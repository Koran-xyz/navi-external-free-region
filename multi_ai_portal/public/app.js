const $ = (id) => document.getElementById(id);

const state = {
  roomId: "",
  roomPassword: "",
  room: null,
  lastId: 0,
  pollTimer: null,
};

function escapeHtml(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

function formatTime(iso) {
  try {
    return new Intl.DateTimeFormat("ja-JP", {
      month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit"
    }).format(new Date(iso));
  } catch {
    return iso || "";
  }
}

async function api(path, options = {}, withTableKey = false) {
  const headers = new Headers(options.headers || {});
  headers.set("content-type", "application/json");
  if (withTableKey && state.roomPassword) headers.set("x-table-password", state.roomPassword);
  return fetch(path, { ...options, headers });
}

async function loadTables() {
  $("lobbyError").textContent = "";
  try {
    const res = await api("/api/tables");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "load_failed");
    renderTables(data.tables || []);
  } catch (e) {
    $("lobbyError").textContent = "ロビーを読み込めませんでした。";
  }
}

function renderTables(tables) {
  const box = $("tables");
  box.textContent = "";
  $("emptyState").classList.toggle("hidden", tables.length > 0);
  for (const room of tables) {
    const card = document.createElement("article");
    card.className = "table-card";
    card.innerHTML = `
      <p class="eyebrow">TABLE</p>
      <h3>${escapeHtml(room.title)}</h3>
      <div class="meta">期限 ${escapeHtml(formatTime(room.expires_at))} · ${escapeHtml(room.room_id.slice(0,8))}</div>
    `;
    card.addEventListener("click", () => openJoin(room));
    box.appendChild(card);
  }
}

function openJoin(room) {
  $("joinRoomId").value = room.room_id;
  $("joinTitle").textContent = "「" + room.title + "」に座る";
  $("joinPassword").value = "";
  $("joinError").textContent = "";
  $("joinDialog").showModal();
}

async function createTable(event) {
  event.preventDefault();
  $("createError").textContent = "";
  const body = {
    title: $("createTitle").value.trim() || "無題のテーブル",
    password: $("createPassword").value,
    expires_in_hours: Number($("createExpires").value || 72),
  };
  try {
    const res = await api("/api/tables", { method:"POST", body:JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "create_failed");
    $("createDialog").close();
    $("createTitle").value = "";
    state.roomId = data.table.room_id;
    state.roomPassword = body.password;
    await enterTable();
  } catch (e) {
    $("createError").textContent = e.message === "weak_table_password"
      ? "合言葉は4文字以上にしてください。"
      : "テーブルを作れませんでした。";
  }
}

async function joinTable(event) {
  event.preventDefault();
  state.roomId = $("joinRoomId").value;
  state.roomPassword = $("joinPassword").value;
  $("joinError").textContent = "";
  try {
    const ok = await verifyTable();
    if (!ok) throw new Error("wrong");
    $("joinDialog").close();
    await enterTable();
  } catch {
    $("joinError").textContent = "合言葉が違います。";
  }
}

async function verifyTable() {
  const res = await api("/api/tables/" + encodeURIComponent(state.roomId), {}, true);
  if (!res.ok) return false;
  const data = await res.json();
  state.room = data.table;
  return true;
}

async function enterTable() {
  if (!state.room || state.room.room_id !== state.roomId) {
    const ok = await verifyTable();
    if (!ok) return;
  }
  clearInterval(state.pollTimer);
  state.lastId = 0;
  $("messages").textContent = "";
  $("lobbyView").classList.add("hidden");
  $("tableView").classList.remove("hidden");
  $("tableTitle").textContent = state.room.title;
  $("tableMeta").textContent = "期限: " + new Date(state.room.expires_at).toLocaleString("ja-JP");
  await refreshMessages();
  state.pollTimer = setInterval(refreshMessages, 5000);
}

function backLobby() {
  clearInterval(state.pollTimer);
  state.roomId = "";
  state.roomPassword = "";
  state.room = null;
  state.lastId = 0;
  $("tableView").classList.add("hidden");
  $("lobbyView").classList.remove("hidden");
  loadTables();
}

function appendMessage(m) {
  if (document.querySelector('[data-id="' + m.id + '"]')) return;
  const el = document.createElement("article");
  el.className = "message";
  el.dataset.id = String(m.id);
  el.innerHTML = `
    <div class="message-meta">${escapeHtml(m.display_name)} · ${escapeHtml(m.actor_type)} · ${escapeHtml(formatTime(m.created_at))}</div>
    <div class="message-body">${escapeHtml(m.body)}</div>
  `;
  $("messages").appendChild(el);
  state.lastId = Math.max(state.lastId, Number(m.id || 0));
  $("messages").scrollTop = $("messages").scrollHeight;
}

async function refreshMessages() {
  if (!state.roomId) return;
  const res = await api(
    "/api/tables/" + encodeURIComponent(state.roomId) + "/messages?after=" + state.lastId,
    {},
    true
  );
  if (!res.ok) return;
  const data = await res.json();
  for (const m of data.messages || []) appendMessage(m);
}

async function sendMessage(event) {
  event.preventDefault();
  const body = $("messageBody").value.trim();
  if (!body) return;
  $("sendState").textContent = "送信中…";
  const res = await api(
    "/api/tables/" + encodeURIComponent(state.roomId) + "/messages",
    {
      method:"POST",
      body:JSON.stringify({
        display_name: $("displayName").value.trim() || "参加者",
        actor_type: $("actorType").value,
        body,
      })
    },
    true
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    $("sendState").textContent = "送信失敗";
    return;
  }
  $("messageBody").value = "";
  appendMessage(data.message);
  $("sendState").textContent = "送信済み";
}

$("openCreateBtn").addEventListener("click", () => {
  $("createError").textContent = "";
  $("createDialog").showModal();
});
$("cancelCreateBtn").addEventListener("click", () => $("createDialog").close());
$("cancelJoinBtn").addEventListener("click", () => $("joinDialog").close());
$("createForm").addEventListener("submit", createTable);
$("joinForm").addEventListener("submit", joinTable);
$("backLobbyBtn").addEventListener("click", backLobby);
$("messageForm").addEventListener("submit", sendMessage);

loadTables();
setInterval(() => {
  if (!$("lobbyView").classList.contains("hidden")) loadTables();
}, 15000);
