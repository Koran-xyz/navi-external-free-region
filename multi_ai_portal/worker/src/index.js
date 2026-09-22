const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
};

function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...JSON_HEADERS, ...extra },
  });
}

function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "*";
  return {
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "authorization,content-type",
    "access-control-max-age": "86400",
    "vary": "Origin",
  };
}

function isoNow() {
  return new Date().toISOString();
}

function addHours(hours) {
  return new Date(Date.now() + hours * 60 * 60 * 1000).toISOString();
}

function addDays(days) {
  return new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString();
}

function safeString(value, max) {
  return String(value ?? "").trim().slice(0, max);
}

function randomToken(bytes = 32) {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return btoa(String.fromCharCode(...arr))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

async function sha256(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function bytesToHex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(hex) {
  return new Uint8Array((hex.match(/.{1,2}/g) || []).map((x) => parseInt(x, 16)));
}

async function derivePassword(password, saltBytes) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      salt: saltBytes,
      iterations: 120000,
      hash: "SHA-256",
    },
    key,
    256
  );
  return bytesToHex(new Uint8Array(bits));
}

async function passwordRecord(password) {
  const salt = new Uint8Array(16);
  crypto.getRandomValues(salt);
  return {
    salt: bytesToHex(salt),
    hash: await derivePassword(password, salt),
  };
}

async function verifyPassword(password, saltHex, expectedHash) {
  const actual = await derivePassword(password, hexToBytes(saltHex));
  if (actual.length !== expectedHash.length) return false;
  let diff = 0;
  for (let i = 0; i < actual.length; i++) diff |= actual.charCodeAt(i) ^ expectedHash.charCodeAt(i);
  return diff === 0;
}

function bearer(request) {
  const raw = request.headers.get("Authorization") || "";
  return raw.startsWith("Bearer ") ? raw.slice(7).trim() : "";
}

async function currentUser(request, env) {
  const token = bearer(request);
  if (!token) return null;
  const tokenHash = await sha256(token);
  const row = await env.DB.prepare(
    `SELECT u.username, u.display_name, u.actor_type, u.team_id, s.expires_at
     FROM sessions s
     JOIN portal_users u ON u.username = s.username
     WHERE s.token_hash = ?`
  ).bind(tokenHash).first();
  if (!row) return null;
  if (Date.parse(row.expires_at) <= Date.now()) {
    await env.DB.prepare("DELETE FROM sessions WHERE token_hash = ?").bind(tokenHash).run();
    return null;
  }
  return { tokenHash, user: row };
}

async function requireUser(request, env) {
  const auth = await currentUser(request, env);
  if (!auth) return { error: json({ error: "login_required" }, 401) };
  return auth;
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

function publicUser(row) {
  return {
    username: row.username,
    display_name: row.display_name,
    actor_type: row.actor_type,
    team_id: row.team_id || null,
  };
}

async function register(request, env) {
  const body = await readJson(request);
  if (!body) return json({ error: "invalid_json" }, 400);

  const username = safeString(body.username, 40).toLowerCase();
  const displayName = safeString(body.display_name, 80);
  const actorType = safeString(body.actor_type || "human", 40);
  const teamId = safeString(body.team_id, 80) || null;
  const password = String(body.password || "");

  if (!/^[a-z0-9_-]{3,40}$/.test(username)) return json({ error: "invalid_username" }, 400);
  if (!displayName) return json({ error: "display_name_required" }, 400);
  if (password.length < 8 || password.length > 128) return json({ error: "weak_password" }, 400);

  const exists = await env.DB.prepare("SELECT username FROM portal_users WHERE username = ?")
    .bind(username).first();
  if (exists) return json({ error: "username_taken" }, 409);

  const pw = await passwordRecord(password);
  const createdAt = isoNow();
  await env.DB.prepare(
    `INSERT INTO portal_users
     (username, display_name, actor_type, team_id, password_salt, password_hash, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).bind(username, displayName, actorType, teamId, pw.salt, pw.hash, createdAt).run();

  const session = await createSession(env, username);
  return json({
    ok: true,
    user: { username, display_name: displayName, actor_type: actorType, team_id: teamId },
    session_token: session.token,
    session_expires_at: session.expiresAt,
  }, 201);
}

async function createSession(env, username) {
  const token = randomToken();
  const hash = await sha256(token);
  const createdAt = isoNow();
  const expiresAt = addDays(7);
  await env.DB.prepare(
    "INSERT INTO sessions (token_hash, username, created_at, expires_at) VALUES (?, ?, ?, ?)"
  ).bind(hash, username, createdAt, expiresAt).run();
  return { token, expiresAt };
}

async function login(request, env) {
  const body = await readJson(request);
  if (!body) return json({ error: "invalid_json" }, 400);
  const username = safeString(body.username, 40).toLowerCase();
  const password = String(body.password || "");
  const row = await env.DB.prepare(
    "SELECT * FROM portal_users WHERE username = ?"
  ).bind(username).first();

  if (!row || !(await verifyPassword(password, row.password_salt, row.password_hash))) {
    return json({ error: "invalid_credentials" }, 401);
  }

  const session = await createSession(env, username);
  return json({
    ok: true,
    user: publicUser(row),
    session_token: session.token,
    session_expires_at: session.expiresAt,
  });
}

async function me(request, env) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;
  return json({ ok: true, user: publicUser(auth.user) });
}

async function logout(request, env) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;
  await env.DB.prepare("DELETE FROM sessions WHERE token_hash = ?").bind(auth.tokenHash).run();
  return json({ ok: true });
}

async function createRoom(request, env) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;

  const body = await readJson(request);
  if (!body) return json({ error: "invalid_json" }, 400);
  const title = safeString(body.title || "一時会議室", 120);
  const requested = Number(body.expires_in_hours || 72);
  const allowed = new Set([24, 72, 168]);
  const hours = allowed.has(requested) ? requested : 72;
  const roomId = crypto.randomUUID();
  const createdAt = isoNow();
  const expiresAt = addHours(hours);

  await env.DB.batch([
    env.DB.prepare(
      "INSERT INTO rooms (room_id, title, owner_username, created_at, expires_at) VALUES (?, ?, ?, ?, ?)"
    ).bind(roomId, title, auth.user.username, createdAt, expiresAt),
    env.DB.prepare(
      "INSERT INTO room_members (room_id, username, role, joined_at) VALUES (?, ?, 'owner', ?)"
    ).bind(roomId, auth.user.username, createdAt),
  ]);

  return json({
    ok: true,
    room: {
      room_id: roomId,
      title,
      owner_username: auth.user.username,
      role: "owner",
      created_at: createdAt,
      expires_at: expiresAt,
    },
  }, 201);
}

async function listRooms(request, env) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;
  const rows = await env.DB.prepare(
    `SELECT r.room_id, r.title, r.owner_username, r.created_at, r.expires_at, m.role
     FROM room_members m
     JOIN rooms r ON r.room_id = m.room_id
     WHERE m.username = ? AND r.expires_at > ?
     ORDER BY r.created_at DESC`
  ).bind(auth.user.username, isoNow()).all();
  return json({ ok: true, rooms: rows.results || [] });
}

async function membership(env, roomId, username) {
  return await env.DB.prepare(
    `SELECT r.room_id, r.title, r.owner_username, r.created_at, r.expires_at, m.role
     FROM rooms r
     JOIN room_members m ON m.room_id = r.room_id
     WHERE r.room_id = ? AND m.username = ?`
  ).bind(roomId, username).first();
}

async function roomInfo(request, env, roomId) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;
  const room = await membership(env, roomId, auth.user.username);
  if (!room) return json({ error: "room_not_found_or_forbidden" }, 404);
  if (Date.parse(room.expires_at) <= Date.now()) return json({ error: "room_expired" }, 410);
  return json({ ok: true, room });
}

async function listMessages(request, env, roomId, url) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;
  const room = await membership(env, roomId, auth.user.username);
  if (!room) return json({ error: "room_not_found_or_forbidden" }, 404);
  if (Date.parse(room.expires_at) <= Date.now()) return json({ error: "room_expired" }, 410);

  const after = Math.max(0, Number(url.searchParams.get("after") || 0));
  const rows = await env.DB.prepare(
    `SELECT m.id, m.room_id, m.username, m.body, m.created_at,
            u.display_name, u.actor_type, u.team_id
     FROM messages m
     JOIN portal_users u ON u.username = m.username
     WHERE m.room_id = ? AND m.id > ?
     ORDER BY m.id ASC
     LIMIT 200`
  ).bind(roomId, after).all();

  return json({ ok: true, room, messages: rows.results || [] });
}

async function postMessage(request, env, roomId) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;
  const room = await membership(env, roomId, auth.user.username);
  if (!room) return json({ error: "room_not_found_or_forbidden" }, 404);
  if (Date.parse(room.expires_at) <= Date.now()) return json({ error: "room_expired" }, 410);

  const body = await readJson(request);
  if (!body) return json({ error: "invalid_json" }, 400);
  const text = safeString(body.body, 8000);
  if (!text) return json({ error: "body_required" }, 400);

  const createdAt = isoNow();
  const result = await env.DB.prepare(
    "INSERT INTO messages (room_id, username, body, created_at) VALUES (?, ?, ?, ?)"
  ).bind(roomId, auth.user.username, text, createdAt).run();

  return json({
    ok: true,
    message: {
      id: result.meta?.last_row_id ?? null,
      room_id: roomId,
      username: auth.user.username,
      display_name: auth.user.display_name,
      actor_type: auth.user.actor_type,
      team_id: auth.user.team_id || null,
      body: text,
      created_at: createdAt,
    },
  }, 201);
}

async function createInvite(request, env, roomId) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;
  const room = await membership(env, roomId, auth.user.username);
  if (!room) return json({ error: "room_not_found_or_forbidden" }, 404);
  if (!["owner", "admin"].includes(room.role)) return json({ error: "invite_not_allowed" }, 403);

  const body = (await readJson(request)) || {};
  const requested = Number(body.expires_in_hours || 24);
  const hours = [1, 6, 24, 72].includes(requested) ? requested : 24;
  const token = randomToken(24);
  const hash = await sha256(token);
  const createdAt = isoNow();
  const expiresAt = addHours(hours);

  await env.DB.prepare(
    `INSERT INTO room_invites
     (invite_hash, room_id, created_by, created_at, expires_at)
     VALUES (?, ?, ?, ?, ?)`
  ).bind(hash, roomId, auth.user.username, createdAt, expiresAt).run();

  return json({
    ok: true,
    invite_token: token,
    expires_at: expiresAt,
  }, 201);
}

async function acceptInvite(request, env) {
  const auth = await requireUser(request, env);
  if (auth.error) return auth.error;
  const body = await readJson(request);
  if (!body) return json({ error: "invalid_json" }, 400);
  const token = safeString(body.invite_token, 200);
  if (!token) return json({ error: "invite_token_required" }, 400);
  const hash = await sha256(token);

  const invite = await env.DB.prepare(
    `SELECT i.*, r.title, r.expires_at AS room_expires_at
     FROM room_invites i
     JOIN rooms r ON r.room_id = i.room_id
     WHERE i.invite_hash = ?`
  ).bind(hash).first();

  if (!invite) return json({ error: "invite_invalid" }, 404);
  if (invite.used_at) return json({ error: "invite_used" }, 409);
  if (Date.parse(invite.expires_at) <= Date.now()) return json({ error: "invite_expired" }, 410);
  if (Date.parse(invite.room_expires_at) <= Date.now()) return json({ error: "room_expired" }, 410);

  const now = isoNow();
  await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO room_members (room_id, username, role, joined_at)
       VALUES (?, ?, 'member', ?)
       ON CONFLICT(room_id, username) DO NOTHING`
    ).bind(invite.room_id, auth.user.username, now),
    env.DB.prepare(
      "UPDATE room_invites SET used_by = ?, used_at = ? WHERE invite_hash = ?"
    ).bind(auth.user.username, now, hash),
  ]);

  return json({
    ok: true,
    room: {
      room_id: invite.room_id,
      title: invite.title,
      expires_at: invite.room_expires_at,
    },
  });
}

function roomRoute(pathname) {
  const match = pathname.match(/^\/api\/rooms\/([0-9a-fA-F-]{36})(?:\/(messages|invites))?$/);
  if (!match) return null;
  return { roomId: match[1], child: match[2] || "" };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    let response;
    try {
      if (url.pathname === "/api/health" && request.method === "GET") {
        response = json({ status: "ok", version: env.PORTAL_VERSION || "0.2.0", time: isoNow() });
      } else if (url.pathname === "/api/auth/register" && request.method === "POST") {
        response = await register(request, env);
      } else if (url.pathname === "/api/auth/login" && request.method === "POST") {
        response = await login(request, env);
      } else if (url.pathname === "/api/auth/me" && request.method === "GET") {
        response = await me(request, env);
      } else if (url.pathname === "/api/auth/logout" && request.method === "POST") {
        response = await logout(request, env);
      } else if (url.pathname === "/api/rooms" && request.method === "GET") {
        response = await listRooms(request, env);
      } else if (url.pathname === "/api/rooms" && request.method === "POST") {
        response = await createRoom(request, env);
      } else if (url.pathname === "/api/invites/accept" && request.method === "POST") {
        response = await acceptInvite(request, env);
      } else {
        const route = roomRoute(url.pathname);
        if (route && !route.child && request.method === "GET") {
          response = await roomInfo(request, env, route.roomId);
        } else if (route && route.child === "messages" && request.method === "GET") {
          response = await listMessages(request, env, route.roomId, url);
        } else if (route && route.child === "messages" && request.method === "POST") {
          response = await postMessage(request, env, route.roomId);
        } else if (route && route.child === "invites" && request.method === "POST") {
          response = await createInvite(request, env, route.roomId);
        } else if (url.pathname.startsWith("/api/")) {
          response = json({ error: "not_found" }, 404);
        } else {
          return env.ASSETS.fetch(request);
        }
      }
    } catch (error) {
      response = json({
        error: "internal_error",
        message: error instanceof Error ? error.message : String(error),
      }, 500);
    }

    const headers = new Headers(response.headers);
    const cors = corsHeaders(request);
    for (const [k, v] of Object.entries(cors)) headers.set(k, v);
    headers.set("x-content-type-options", "nosniff");
    headers.set("referrer-policy", "no-referrer");
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
