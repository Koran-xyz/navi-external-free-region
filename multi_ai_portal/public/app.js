const $ = (id) => document.getElementById(id);

const state = {
  roomId: "",
  roomKey: "",
  lastId: 0,
  pollTimer: null,
  room: null,
};

function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("content-type", "application/json");
  if (state.roomKey) headers.set("authorization", "Bearer " + state.roomKey);
  return fetch(path, { ...options, headers });
}

function inviteUrl() {
  const url = new URL(location.href);
  url.search = "";
  url.hash = "";
  url.searchParams.set("room", state.roomId);
  url.hash = "key=" + encodeURIComponent(state.roomKey);
  return url.toString();
}

function parseInvite() {
  const url = new URL(location.href);
  const roomId = url.searchParams.get("room") || "";
  const hash = new URLSearchParams(url.hash.replace(/^#/, ""));
  const key = hash.get("key") || "";
  return { roomId, key };
}

function setConnected(connected) {
  $("startPanel").classList.toggle("hidden", connected);
  $("roomPanel").classList.toggle("hidden", !connected);
  $("connectionBadge").textContent = connected ? "接続中" : "未接続";
}

function formatTime(iso) {
  try {
    return new Intl.DateTimeFormat("ja-JP", {
      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"
    }).format(new Date(iso));
  } catch {
    return iso || "";
  }
}

function appendMessage(m) {
  if (document.querySelector('[data-message-id="' + m.id + '"]')) return;
  const box = document.createElement("article");
  box.className = "message";
  box.dataset.messageId = String(m.id);

  const meta = document.createElement("div");
  meta.className = "message-meta";
  const parts = [
    m.sender_name,
    m.sender_type,
    m.team_id || "",
    formatTime(m.created_at),
  ].filter(Boolean);
  meta.textContent = parts.join(" · ");

  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = m.body;

  box.append(meta, body);
  $("messages").appendChild(box);
  state.lastId = Math.max(state.lastId, Number(m.id || 0));
  $("messages").scrollTop = $("messages").scrollHeight;
}

async function refreshMessages() {
  if (!state.roomId || !state.roomKey) return;
  $("pollState").textContent = "更新中…";
  try {
    const res = await api("/api/rooms/" + state.roomId + "/messages?after=" + state.lastId);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "load_failed");
    state.room = data.room;
    $("currentRoomTitle").textContent = data.room.title || "会議室";
    $("roomMeta").textContent = "期限: " + new Date(data.room.expires_at).toLocaleString("ja-JP");
    for (const m of data.messages || []) appendMessage(m);
    $("pollState").textContent = "同期済み";
  } catch (error) {
    $("pollState").textContent = "更新失敗: " + error.message;
  }
}

function startPolling() {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(refreshMessages, 5000);
}

async function connect(roomId, key) {
  state.roomId = roomId.trim();
  state.roomKey = key.trim();
  state.lastId = 0;
  $("messages").textContent = "";
  if (!state.roomId || !state.roomKey) throw new Error("会議室IDとキーが必要です");

  const res = await api("/api/rooms/" + state.roomId);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "接続できませんでした");

  state.room = data.room;
  $("currentRoomTitle").textContent = data.room.title;
  $("roomMeta").textContent = "期限: " + new Date(data.room.expires_at).toLocaleString("ja-JP");
  setConnected(true);
  await refreshMessages();
  startPolling();
}

async function createRoom() {
  $("startError").textContent = "";
  try {
    const res = await fetch("/api/rooms", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        title: $("roomTitle").value || "一時会議室",
        expires_in_hours: Number($("expires").value || 72),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "作成できませんでした");

    const url = new URL(location.href);
    url.search = "";
    url.hash = "";
    url.searchParams.set("room", data.room.room_id);
    url.hash = "key=" + encodeURIComponent(data.room_key);
    history.replaceState({}, "", url);

    await connect(data.room.room_id, data.room_key);
  } catch (error) {
    $("startError").textContent = error.message;
  }
}

async function sendMessage(event) {
  event.preventDefault();
  const body = $("messageBody").value.trim();
  if (!body) return;

  $("sendState").textContent = "送信中…";
  try {
    const res = await api("/api/rooms/" + state.roomId + "/messages", {
      method: "POST",
      body: JSON.stringify({
        sender_name: $("senderName").value || "参加者",
        sender_type: $("senderType").value,
        team_id: $("teamId").value || null,
        body,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "送信できませんでした");
    $("messageBody").value = "";
    if (data.message) appendMessage(data.message);
    $("sendState").textContent = "追記済み";
  } catch (error) {
    $("sendState").textContent = "失敗: " + error.message;
  }
}

$("createRoomBtn").addEventListener("click", createRoom);
$("joinRoomBtn").addEventListener("click", async () => {
  $("startError").textContent = "";
  try {
    await connect($("manualRoomId").value, $("manualRoomKey").value);
  } catch (error) {
    $("startError").textContent = error.message;
  }
});
$("messageForm").addEventListener("submit", sendMessage);
$("copyInviteBtn").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(inviteUrl());
    $("copyInviteBtn").textContent = "コピー済み";
    setTimeout(() => $("copyInviteBtn").textContent = "招待URLをコピー", 1400);
  } catch {
    prompt("このURLをコピーしてください", inviteUrl());
  }
});
$("leaveBtn").addEventListener("click", () => {
  clearInterval(state.pollTimer);
  state.roomId = "";
  state.roomKey = "";
  state.room = null;
  state.lastId = 0;
  const url = new URL(location.href);
  url.search = "";
  url.hash = "";
  history.replaceState({}, "", url);
  setConnected(false);
});

(async () => {
  const invite = parseInvite();
  if (invite.roomId && invite.key) {
    try {
      await connect(invite.roomId, invite.key);
    } catch (error) {
      $("startError").textContent = "招待URLに接続できません: " + error.message;
      setConnected(false);
    }
  }
})();
