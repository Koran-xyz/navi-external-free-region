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

function randomToken(bytes = 24) {
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

function bearer(request) {
  const raw = request.headers.get("Authorization") || "";
  if (!raw.startsWith("Bearer ")) return "";
  return raw.slice(7).trim();
}

function safeString(value, max) {
  return String(value ?? "").trim().slice(0, max);
}

async function getRoom(env, roomId) {
  return await env.DB.prepare(
    "SELECT room_id, title, token_hash, created_at, expires_at FROM rooms WHERE room_id = ?"
  ).bind(roomId).first();
}

function expired(room) {
  return !room || Date.parse(room.expires_at) <= Date.now();
}

async function authorizeRoom(request, env, roomId) {
  const room = await getRoom(env, roomId);
  if (!room) return { error: json({ error: "room_not_found" }, 404) };
  if (expired(room)) return { error: json({ error: "room_expired" }, 410) };

  const token = bearer(request);
  if (!token) return { error: json({ error: "authorization_required" }, 401) };

  const hash = await sha256(token);
  if (hash !== room.token_hash) {
    return { error: json({ error: "invalid_room_key" }, 403) };
  }
  return { room };
}

async function createRoom(request, env) {
  let body = {};
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }

  const title = safeString(body.title || "一時会議室", 120);
  const requested = Number(body.expires_in_hours || 72);
  const allowed = new Set([24, 72, 168]);
  const hours = allowed.has(requested) ? requested : 72;

  const roomId = crypto.randomUUID();
  const roomKey = randomToken();
  const tokenHash = await sha256(roomKey);
  const createdAt = isoNow();
  const expiresAt = addHours(hours);

  await env.DB.prepare(
    "INSERT INTO rooms (room_id, title, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?)"
  ).bind(roomId, title, tokenHash, createdAt, expiresAt).run();

  return json({
    ok: true,
    room: {
      room_id: roomId,
      title,
      created_at: createdAt,
      expires_at: expiresAt,
    },
    room_key: roomKey,
  }, 201);
}

async function roomInfo(request, env, roomId) {
  const auth = await authorizeRoom(request, env, roomId);
  if (auth.error) return auth.error;
  const { token_hash, ...publicRoom } = auth.room;
  return json({ ok: true, room: publicRoom });
}

async function listMessages(request, env, roomId, url) {
  const auth = await authorizeRoom(request, env, roomId);
  if (auth.error) return auth.error;

  const after = Math.max(0, Number(url.searchParams.get("after") || 0));
  const rows = await env.DB.prepare(
    `SELECT id, room_id, sender_name, sender_type, team_id, body, created_at
     FROM messages
     WHERE room_id = ? AND id > ?
     ORDER BY id ASC
     LIMIT 200`
  ).bind(roomId, after).all();

  return json({
    ok: true,
    room: {
      room_id: auth.room.room_id,
      title: auth.room.title,
      expires_at: auth.room.expires_at,
    },
    messages: rows.results || [],
  });
}

async function postMessage(request, env, roomId) {
  const auth = await authorizeRoom(request, env, roomId);
  if (auth.error) return auth.error;

  let body = {};
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }

  const senderName = safeString(body.sender_name, 80);
  const senderType = safeString(body.sender_type || "other", 40);
  const teamId = safeString(body.team_id, 80) || null;
  const text = safeString(body.body, 8000);

  if (!senderName || !text) {
    return json({ error: "sender_name_and_body_required" }, 400);
  }

  const createdAt = isoNow();
  const result = await env.DB.prepare(
    `INSERT INTO messages
      (room_id, sender_name, sender_type, team_id, body, created_at)
      VALUES (?, ?, ?, ?, ?, ?)`
  ).bind(roomId, senderName, senderType, teamId, text, createdAt).run();

  return json({
    ok: true,
    message: {
      id: result.meta?.last_row_id ?? null,
      room_id: roomId,
      sender_name: senderName,
      sender_type: senderType,
      team_id: teamId,
      body: text,
      created_at: createdAt,
    },
  }, 201);
}

function routeRoom(pathname) {
  const match = pathname.match(/^\/api\/rooms\/([0-9a-fA-F-]{36})(?:\/(messages))?$/);
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
        response = json({
          status: "ok",
          version: env.PORTAL_VERSION || "0.1.0",
          time: isoNow(),
        });
      } else if (url.pathname === "/api/rooms" && request.method === "POST") {
        response = await createRoom(request, env);
      } else {
        const route = routeRoom(url.pathname);
        if (route && !route.child && request.method === "GET") {
          response = await roomInfo(request, env, route.roomId);
        } else if (route && route.child === "messages" && request.method === "GET") {
          response = await listMessages(request, env, route.roomId, url);
        } else if (route && route.child === "messages" && request.method === "POST") {
          response = await postMessage(request, env, route.roomId);
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
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
