const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}

function nowIso() { return new Date().toISOString(); }
function addHours(h) { return new Date(Date.now() + h * 3600000).toISOString(); }
function safe(v, max) { return String(v ?? "").trim().slice(0, max); }

function bytesToHex(bytes) {
  return [...bytes].map(b => b.toString(16).padStart(2, "0")).join("");
}
function hexToBytes(hex) {
  return new Uint8Array((hex.match(/.{1,2}/g) || []).map(x => parseInt(x, 16)));
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
    { name:"PBKDF2", salt:saltBytes, iterations:120000, hash:"SHA-256" },
    key,
    256
  );
  return bytesToHex(new Uint8Array(bits));
}
async function createPasswordRecord(password) {
  const salt = new Uint8Array(16);
  crypto.getRandomValues(salt);
  return { salt: bytesToHex(salt), hash: await derivePassword(password, salt) };
}
async function verifyPassword(password, saltHex, expected) {
  const actual = await derivePassword(password, hexToBytes(saltHex));
  if (actual.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < actual.length; i++) diff |= actual.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}
async function readJson(request) {
  try { return await request.json(); } catch { return null; }
}
function tablePassword(request) {
  return request.headers.get("x-table-password") || "";
}

async function getTable(env, roomId) {
  return await env.DB.prepare(
    "SELECT room_id,title,password_salt,password_hash,created_at,expires_at FROM cafe_tables WHERE room_id=?"
  ).bind(roomId).first();
}

async function authorizeTable(request, env, roomId) {
  const table = await getTable(env, roomId);
  if (!table) return { error: json({error:"table_not_found"},404) };
  if (Date.parse(table.expires_at) <= Date.now()) return { error: json({error:"table_expired"},410) };
  const password = tablePassword(request);
  if (!password) return { error: json({error:"table_password_required"},401) };
  const ok = await verifyPassword(password, table.password_salt, table.password_hash);
  if (!ok) return { error: json({error:"invalid_table_password"},403) };
  return { table };
}

async function listTables(env) {
  const rows = await env.DB.prepare(
    `SELECT room_id,title,created_at,expires_at
     FROM cafe_tables
     WHERE expires_at > ?
     ORDER BY created_at DESC
     LIMIT 100`
  ).bind(nowIso()).all();
  return json({ ok:true, tables:rows.results || [] });
}

async function createTable(request, env) {
  const body = await readJson(request);
  if (!body) return json({error:"invalid_json"},400);
  const title = safe(body.title || "無題のテーブル",80);
  const password = String(body.password || "");
  if (password.length < 4 || password.length > 64) {
    return json({error:"weak_table_password"},400);
  }
  const requested = Number(body.expires_in_hours || 72);
  const allowed = new Set([24,72,168]);
  const hours = allowed.has(requested) ? requested : 72;
  const roomId = crypto.randomUUID();
  const pw = await createPasswordRecord(password);
  const createdAt = nowIso();
  const expiresAt = addHours(hours);

  await env.DB.prepare(
    `INSERT INTO cafe_tables
     (room_id,title,password_salt,password_hash,created_at,expires_at)
     VALUES (?,?,?,?,?,?)`
  ).bind(roomId,title,pw.salt,pw.hash,createdAt,expiresAt).run();

  return json({
    ok:true,
    table:{room_id:roomId,title,created_at:createdAt,expires_at:expiresAt}
  },201);
}

async function tableInfo(request, env, roomId) {
  const auth = await authorizeTable(request,env,roomId);
  if (auth.error) return auth.error;
  const { password_salt, password_hash, ...table } = auth.table;
  return json({ok:true,table});
}

async function listMessages(request, env, roomId, url) {
  const auth = await authorizeTable(request,env,roomId);
  if (auth.error) return auth.error;
  const after = Math.max(0,Number(url.searchParams.get("after") || 0));
  const rows = await env.DB.prepare(
    `SELECT id,room_id,display_name,actor_type,body,created_at
     FROM cafe_messages
     WHERE room_id=? AND id>?
     ORDER BY id ASC
     LIMIT 200`
  ).bind(roomId,after).all();
  return json({ok:true,messages:rows.results || []});
}

async function postMessage(request, env, roomId) {
  const auth = await authorizeTable(request,env,roomId);
  if (auth.error) return auth.error;
  const body = await readJson(request);
  if (!body) return json({error:"invalid_json"},400);
  const displayName = safe(body.display_name || "参加者",60);
  const actorType = safe(body.actor_type || "other",30);
  const text = safe(body.body,8000);
  if (!text) return json({error:"body_required"},400);
  const createdAt = nowIso();
  const result = await env.DB.prepare(
    `INSERT INTO cafe_messages
     (room_id,display_name,actor_type,body,created_at)
     VALUES (?,?,?,?,?)`
  ).bind(roomId,displayName,actorType,text,createdAt).run();

  return json({
    ok:true,
    message:{
      id:result.meta?.last_row_id ?? null,
      room_id:roomId,
      display_name:displayName,
      actor_type:actorType,
      body:text,
      created_at:createdAt
    }
  },201);
}

function tableRoute(pathname) {
  const m = pathname.match(/^\/api\/tables\/([0-9a-fA-F-]{36})(?:\/(messages))?$/);
  if (!m) return null;
  return { roomId:m[1], child:m[2] || "" };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/api/health" && request.method === "GET") {
        return json({status:"ok",version:env.PORTAL_VERSION || "0.3.0"});
      }
      if (url.pathname === "/api/tables" && request.method === "GET") {
        return await listTables(env);
      }
      if (url.pathname === "/api/tables" && request.method === "POST") {
        return await createTable(request,env);
      }

      const route = tableRoute(url.pathname);
      if (route && !route.child && request.method === "GET") {
        return await tableInfo(request,env,route.roomId);
      }
      if (route && route.child === "messages" && request.method === "GET") {
        return await listMessages(request,env,route.roomId,url);
      }
      if (route && route.child === "messages" && request.method === "POST") {
        return await postMessage(request,env,route.roomId);
      }

      if (url.pathname.startsWith("/api/")) return json({error:"not_found"},404);
      return env.ASSETS.fetch(request);
    } catch (e) {
      return json({error:"internal_error"},500);
    }
  }
};
