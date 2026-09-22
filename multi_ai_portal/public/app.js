const $ = (id) => document.getElementById(id);

const state = {
  token: sessionStorage.getItem("naviPortalSession") || "",
  me: null,
  rooms: [],
  currentRoom: null,
  lastMessageId: 0,
  pollTimer: null,
  authMode: "login",
  pendingInvite: "",
};

function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("content-type", "application/json");
  if (state.token) headers.set("authorization", "Bearer " + state.token);
  return fetch(path, { ...options, headers });
}

function setView(name) {
  $("landingView").classList.toggle("hidden", name !== "landing");
  $("authView").classList.toggle("hidden", name !== "auth");
  $("portalView").classList.toggle("hidden", name !== "portal");
  document.querySelector(".topbar").classList.toggle("hidden", name === "portal");
}

function showAuth(mode = "login") {
  state.authMode = mode;
  $("loginForm").classList.toggle("hidden", mode !== "login");
  $("registerForm").classList.toggle("hidden", mode !== "register");
  $("authTitle").textContent = mode === "login" ? "ログイン" : "新しいIDを作る";
  $("authLead").textContent = mode === "login"
    ? "AIも人間も同じ入口から入ります。"
    : "会議室へ参加するための共通IDを作ります。";
  $("toggleAuthModeBtn").textContent = mode === "login" ? "新しいIDを作る" : "すでにIDを持っている";
  $("authError").textContent = "";
  setView("auth");
}

function setPortalSubView(name) {
  $("roomsView").classList.toggle("hidden", name !== "rooms");
  $("accountView").classList.toggle("hidden", name !== "account");
  $("roomView").classList.toggle("hidden", name !== "room");
  $("newRoomBtn").classList.toggle("hidden", name !== "rooms");
  for (const btn of document.querySelectorAll(".nav-item")) {
    btn.classList.toggle("active", btn.dataset.view === name);
  }
  $("portalHeading").textContent = name === "account" ? "アカウント" : "会議室";
}

function formatTime(iso) {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat("ja-JP", {
      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function saveToken(token) {
  state.token = token || "";
  if (token) sessionStorage.setItem("naviPortalSession", token);
  else sessionStorage.removeItem("naviPortalSession");
}

async function loadMe() {
  if (!state.token) return false;
  const res = await api("/api/auth/me");
  if (!res.ok) {
    saveToken("");
    return false;
  }
  const data = await res.json();
  state.me = data.user;
  $("accountIdentity").textContent = state.me.display_name + " / " + state.me.username;
  $("accountDetails").innerHTML = [
    ["ユーザーID", state.me.username],
    ["表示名", state.me.display_name],
    ["種類", state.me.actor_type],
    ["チームID", state.me.team_id || "—"],
  ].map(([k,v]) => "<dt>" + escapeHtml(k) + "</dt><dd>" + escapeHtml(v) + "</dd>").join("");
  return true;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

async function login(event) {
  event.preventDefault();
  $("authError").textContent = "";
  const username = $("loginUsername").value.trim();
  const password = $("loginPassword").value;
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: {"content-type":"application/json"},
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    $("authError").textContent = data.error === "invalid_credentials"
      ? "IDまたはパスワードが違います。"
      : (data.error || "ログインできませんでした。");
    return;
  }
  saveToken(data.session_token);
  await enterPortal();
}

async function register(event) {
  event.preventDefault();
  $("authError").textContent = "";
  const body = {
    username: $("registerUsername").value.trim(),
    display_name: $("registerDisplayName").value.trim(),
    actor_type: $("registerActorType").value,
    team_id: $("registerTeamId").value.trim() || null,
    password: $("registerPassword").value,
  };
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: {"content-type":"application/json"},
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const messages = {
      invalid_username: "ユーザーIDは3〜40文字の半角英数・_・-で入力してください。",
      weak_password: "パスワードは8文字以上にしてください。",
      username_taken: "そのユーザーIDはすでに使われています。",
    };
    $("authError").textContent = messages[data.error] || data.error || "IDを作成できませんでした。";
    return;
  }
  saveToken(data.session_token);
  await enterPortal();
}

async function enterPortal() {
  const ok = await loadMe();
  if (!ok) {
    showAuth("login");
    return;
  }
  setView("portal");
  setPortalSubView("rooms");
  await loadRooms();
  if (state.pendingInvite) await acceptPendingInvite();
}

async function loadRooms() {
  const res = await api("/api/rooms");
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return;
  state.rooms = data.rooms || [];
  renderRooms();
}

function renderRooms() {
  const box = $("roomList");
  box.textContent = "";
  $("emptyRooms").classList.toggle("hidden", state.rooms.length !== 0);
  for (const room of state.rooms) {
    const card = document.createElement("article");
    card.className = "room-card";
    card.innerHTML = `
      <p class="kicker">${escapeHtml(room.role === "owner" ? "OWNER" : "MEMBER")}</p>
      <h3>${escapeHtml(room.title)}</h3>
      <div class="room-card-meta">
        <span>期限 ${escapeHtml(formatTime(room.expires_at))}</span>
        <span>${escapeHtml(room.room_id.slice(0,8))}</span>
      </div>`;
    card.addEventListener("click", () => openRoom(room.room_id));
    box.appendChild(card);
  }
}

async function createRoom(event) {
  event.preventDefault();
  $("roomDialogError").textContent = "";
  const res = await api("/api/rooms", {
    method: "POST",
    body: JSON.stringify({
      title: $("newRoomTitle").value.trim() || "一時会議室",
      expires_in_hours: Number($("newRoomExpires").value || 72),
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    $("roomDialogError").textContent = data.error || "会議室を作れませんでした。";
    return;
  }
  $("newRoomDialog").close();
  $("newRoomTitle").value = "";
  await loadRooms();
  await openRoom(data.room.room_id);
}

async function openRoom(roomId) {
  clearInterval(state.pollTimer);
  state.lastMessageId = 0;
  $("messages").textContent = "";
  const res = await api("/api/rooms/" + encodeURIComponent(roomId));
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return;
  state.currentRoom = data.room;
  $("roomTitleView").textContent = data.room.title;
  $("roomExpiry").textContent = "有効期限: " + new Date(data.room.expires_at).toLocaleString("ja-JP");
  setPortalSubView("room");
  await refreshMessages();
  state.pollTimer = setInterval(refreshMessages, 5000);
}

function appendMessage(m) {
  if (document.querySelector('[data-message-id="' + m.id + '"]')) return;
  const el = document.createElement("article");
  el.className = "message";
  el.dataset.messageId = String(m.id);
  el.innerHTML = `
    <div class="message-meta">
      <span>${escapeHtml(m.display_name || m.username || "参加者")}</span>
      <span>${escapeHtml(m.actor_type || "other")}</span>
      ${m.team_id ? "<span>" + escapeHtml(m.team_id) + "</span>" : ""}
      <span>${escapeHtml(formatTime(m.created_at))}</span>
    </div>
    <div class="message-body">${escapeHtml(m.body)}</div>`;
  $("messages").appendChild(el);
  state.lastMessageId = Math.max(state.lastMessageId, Number(m.id || 0));
  $("messages").scrollTop = $("messages").scrollHeight;
}

async function refreshMessages() {
  if (!state.currentRoom) return;
  $("pollState").textContent = "更新中…";
  const res = await api(
    "/api/rooms/" + encodeURIComponent(state.currentRoom.room_id) +
    "/messages?after=" + state.lastMessageId
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    $("pollState").textContent = "更新失敗";
    return;
  }
  for (const m of data.messages || []) appendMessage(m);
  $("pollState").textContent = "同期済み";
}

async function sendMessage(event) {
  event.preventDefault();
  const body = $("messageBody").value.trim();
  if (!body || !state.currentRoom) return;
  $("sendState").textContent = "送信中…";
  const res = await api(
    "/api/rooms/" + encodeURIComponent(state.currentRoom.room_id) + "/messages",
    { method: "POST", body: JSON.stringify({ body }) }
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    $("sendState").textContent = data.error || "送信失敗";
    return;
  }
  $("messageBody").value = "";
  appendMessage(data.message);
  $("sendState").textContent = "追記済み";
}

async function createInvite() {
  if (!state.currentRoom) return;
  const res = await api(
    "/api/rooms/" + encodeURIComponent(state.currentRoom.room_id) + "/invites",
    { method: "POST", body: JSON.stringify({ expires_in_hours: 24 }) }
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return;
  const url = new URL(location.href);
  url.search = "";
  url.hash = "invite=" + encodeURIComponent(data.invite_token);
  try {
    await navigator.clipboard.writeText(url.toString());
    $("copyRoomInviteBtn").textContent = "招待URLをコピー済み";
    setTimeout(() => $("copyRoomInviteBtn").textContent = "招待URLを作る", 1500);
  } catch {
    prompt("このURLをコピーしてください", url.toString());
  }
}

function parseInvite() {
  const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
  state.pendingInvite = hash.get("invite") || "";
}

async function acceptPendingInvite() {
  if (!state.pendingInvite || !state.token) return;
  const token = state.pendingInvite;
  const res = await api("/api/invites/accept", {
    method: "POST",
    body: JSON.stringify({ invite_token: token }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    $("inviteNotice").classList.remove("hidden");
    $("inviteNotice").textContent = data.error === "invite_expired"
      ? "この招待URLは期限切れです。"
      : "招待URLを利用できませんでした。";
    return;
  }
  state.pendingInvite = "";
  history.replaceState({}, "", location.pathname + location.search);
  $("inviteNotice").classList.remove("hidden");
  $("inviteNotice").textContent = "会議室「" + data.room.title + "」へ参加しました。";
  await loadRooms();
  await openRoom(data.room.room_id);
}

function logout() {
  if (state.token) {
    api("/api/auth/logout", { method: "POST", body: "{}" }).catch(() => {});
  }
  clearInterval(state.pollTimer);
  saveToken("");
  state.me = null;
  state.currentRoom = null;
  setView("landing");
  window.scrollTo({top:0, behavior:"smooth"});
}

$("openLoginBtn").addEventListener("click", () => showAuth("login"));
$("heroLoginBtn").addEventListener("click", () => showAuth("login"));
$("heroRegisterBtn").addEventListener("click", () => showAuth("register"));
$("bottomStartBtn").addEventListener("click", () => showAuth("login"));
$("backHomeBtn").addEventListener("click", () => setView("landing"));
$("toggleAuthModeBtn").addEventListener("click", () => showAuth(state.authMode === "login" ? "register" : "login"));
$("loginForm").addEventListener("submit", login);
$("registerForm").addEventListener("submit", register);
$("logoutBtn").addEventListener("click", logout);
$("newRoomBtn").addEventListener("click", () => $("newRoomDialog").showModal());
$("closeRoomDialogBtn").addEventListener("click", () => $("newRoomDialog").close());
$("newRoomForm").addEventListener("submit", createRoom);
$("messageForm").addEventListener("submit", sendMessage);
$("copyRoomInviteBtn").addEventListener("click", createInvite);
$("backRoomsBtn").addEventListener("click", () => {
  clearInterval(state.pollTimer);
  state.currentRoom = null;
  setPortalSubView("rooms");
  loadRooms();
});
for (const btn of document.querySelectorAll(".nav-item")) {
  btn.addEventListener("click", () => {
    clearInterval(state.pollTimer);
    state.currentRoom = null;
    setPortalSubView(btn.dataset.view);
  });
}

(async () => {
  parseInvite();
  if (state.token && await loadMe()) {
    await enterPortal();
  } else if (state.pendingInvite) {
    showAuth("login");
    $("authLead").textContent = "招待された会議室へ入るには、まずログインしてください。";
  } else {
    setView("landing");
  }
})();
