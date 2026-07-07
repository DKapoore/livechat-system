const socket = io();
let currentChatId = null;
let cannedCache = [];
let adminsCache = [];

socket.on("connect", () => socket.emit("join_admin_room", {}));

// ---------------------------------------------------------------------------
// Bootstrapping
// ---------------------------------------------------------------------------

async function preload() {
  try {
    const [cannedRes, adminsRes] = await Promise.all([
      fetch("/admin/api/canned"),
      fetch("/admin/api/admins"),
    ]);
    if (cannedRes.ok) cannedCache = (await cannedRes.json()).replies;
    if (adminsRes.ok) adminsCache = (await adminsRes.json()).admins;
  } catch (e) { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Conversation list
// ---------------------------------------------------------------------------

async function loadConversations() {
  const status = document.getElementById("convStatusFilter").value;
  const search = document.getElementById("convSearch").value;
  const res = await fetch(`/admin/api/chats?status=${encodeURIComponent(status)}&search=${encodeURIComponent(search)}`);
  if (!res.ok) return;
  const data = await res.json();
  renderConversations(data.chats);
}

function renderConversations(chats) {
  const container = document.getElementById("convItems");
  container.innerHTML = "";
  chats.forEach((c) => {
    const div = document.createElement("div");
    div.className = "conv-item" + (c.chat_id === currentChatId ? " active" : "");
    div.innerHTML = `
      <div>
        <div class="conv-item-name">
          <span class="${c.is_online ? "online-dot" : "offline-dot"}"></span>
          ${escapeHtml(c.visitor_name)} ${c.is_vip ? "⭐" : ""}
        </div>
        <div class="conv-item-preview">${escapeHtml(c.last_message || "No messages yet")}</div>
      </div>
      ${c.unread_count > 0 ? `<span class="conv-item-badge">${c.unread_count}</span>` : ""}
    `;
    div.addEventListener("click", () => openChat(c.chat_id));
    container.appendChild(div);
  });
}

document.getElementById("convSearch").addEventListener("input", debounce(loadConversations, 300));
document.getElementById("convStatusFilter").addEventListener("change", loadConversations);

// ---------------------------------------------------------------------------
// Opening a chat
// ---------------------------------------------------------------------------

async function openChat(chatId) {
  currentChatId = chatId;
  document.getElementById("chatEmptyState").style.display = "none";
  document.getElementById("chatActive").style.display = "flex";

  socket.emit("join_chat_room", { chat_id: chatId });

  const res = await fetch(`/admin/api/chats/${chatId}`);
  const data = await res.json();

  document.getElementById("chatVisitorName").textContent = data.visitor.name || data.visitor.visitor_uid;
  document.getElementById("chatVisitorStatus").textContent =
    (data.visitor.is_online ? "🟢 Online" : "⚪ Offline") + " · " + data.visitor.visitor_uid;

  renderMessages(data.messages);
  renderVisitorPanel(data.visitor);
  populateAssignSelect(data.assigned_admin_id);
  loadConversations();

  socket.emit("message_seen", { chat_id: chatId, sender_type: "admin" });
}

function renderMessages(messages) {
  const container = document.getElementById("messagesContainer");
  container.innerHTML = "";
  messages.forEach((m) => container.appendChild(buildMessageEl(m)));
  container.scrollTop = container.scrollHeight;
}

function buildMessageEl(m) {
  const row = document.createElement("div");
  row.className = `msg-row from-${m.sender_type}`;
  row.dataset.messageId = m.id;
  const time = new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const seenLabel = m.sender_type === "admin" ? (m.status === "seen" ? "Seen" : m.status === "delivered" ? "Delivered" : "Sent") : "";
  row.innerHTML = `
    <div class="msg-bubble${m.is_pinned ? " msg-pinned" : ""}">${escapeHtml(m.content)}</div>
    <div class="msg-meta">${time}${seenLabel ? " · " + seenLabel : ""}</div>
  `;
  return row;
}

function renderVisitorPanel(v) {
  const panel = document.getElementById("visitorPanel");
  const tags = (v.tags || []).map((t) => `<span class="tag-pill">${escapeHtml(t)}</span>`).join("");
  panel.innerHTML = `
    <div class="visitor-field"><div class="visitor-field-label">Name</div><div class="visitor-field-value">${escapeHtml(v.name || "—")}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Visitor ID</div><div class="visitor-field-value">${v.visitor_uid}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Mobile</div><div class="visitor-field-value">${escapeHtml(v.mobile || "—")}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Email</div><div class="visitor-field-value">${escapeHtml(v.email || "—")}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Company</div><div class="visitor-field-value">${escapeHtml(v.company || "—")}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Browser / OS</div><div class="visitor-field-value">${v.browser} / ${v.os}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Device</div><div class="visitor-field-value">${v.device}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Language</div><div class="visitor-field-value">${v.language || "—"}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">IP Address</div><div class="visitor-field-value">${v.ip_address || "—"}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Current Page</div><div class="visitor-field-value">${escapeHtml(v.current_page || "—")}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Visit Count</div><div class="visitor-field-value">${v.visit_count}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Lead Score</div><div class="visitor-field-value">${v.lead_score}</div></div>
    <div class="visitor-field"><div class="visitor-field-label">Tags</div><div class="visitor-field-value">${tags || "—"}</div></div>
  `;
}

function populateAssignSelect(currentAdminId) {
  const select = document.getElementById("assignSelect");
  select.innerHTML = `<option value="">Unassigned</option>` +
    adminsCache.map((a) => `<option value="${a.id}">${escapeHtml(a.name)}${a.is_online ? " 🟢" : ""}</option>`).join("");
  select.value = currentAdminId || "";
}

document.getElementById("assignSelect").addEventListener("change", async (e) => {
  if (!currentChatId) return;
  await fetch(`/admin/api/chats/${currentChatId}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ admin_id: e.target.value || null }),
  });
  loadConversations();
});

// ---------------------------------------------------------------------------
// Sending messages
// ---------------------------------------------------------------------------

document.getElementById("btnSend").addEventListener("click", sendMessage);
document.getElementById("messageInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

function sendMessage() {
  const input = document.getElementById("messageInput");
  const content = input.value.trim();
  if (!content || !currentChatId) return;
  socket.emit("send_message", { chat_id: currentChatId, sender_type: "admin", content });
  input.value = "";
  hideCannedSuggestions();
  socket.emit("typing", { chat_id: currentChatId, sender_type: "admin", is_typing: false });
}

document.getElementById("messageInput").addEventListener("input", (e) => {
  const val = e.target.value;
  if (currentChatId) {
    socket.emit("typing", { chat_id: currentChatId, sender_type: "admin", is_typing: val.length > 0 });
  }
  if (val.startsWith("/") && val.length > 1) {
    showCannedSuggestions(val);
  } else {
    hideCannedSuggestions();
  }
});

function showCannedSuggestions(val) {
  const box = document.getElementById("cannedSuggestions");
  const matches = cannedCache.filter((c) => c.shortcut.startsWith(val));
  if (!matches.length) { hideCannedSuggestions(); return; }
  box.innerHTML = matches
    .map((c) => `<div class="canned-suggestion-item" data-msg="${escapeAttr(c.message)}">${c.shortcut} — ${escapeHtml(c.message).slice(0, 60)}</div>`)
    .join("");
  box.style.display = "block";
  box.querySelectorAll(".canned-suggestion-item").forEach((el) => {
    el.addEventListener("click", () => {
      document.getElementById("messageInput").value = el.dataset.msg;
      hideCannedSuggestions();
      document.getElementById("messageInput").focus();
    });
  });
}
function hideCannedSuggestions() {
  document.getElementById("cannedSuggestions").style.display = "none";
}

// ---------------------------------------------------------------------------
// Socket events
// ---------------------------------------------------------------------------

socket.on("new_message", (msg) => {
  if (msg.chat_id === currentChatId) {
    const container = document.getElementById("messagesContainer");
    container.appendChild(buildMessageEl(msg));
    container.scrollTop = container.scrollHeight;
    socket.emit("message_seen", { chat_id: currentChatId, sender_type: "admin" });
  }
  if (msg.sender_type === "visitor") {
    LC_playNotifySound();
    LC_desktopNotify("New message", msg.content);
  }
});

socket.on("inbox_update", () => loadConversations());

socket.on("typing_status_inbox", (data) => {
  if (data.chat_id === currentChatId) {
    document.getElementById("typingIndicator").style.display = data.is_typing ? "block" : "none";
  }
});

socket.on("messages_seen", (data) => {
  if (data.chat_id === currentChatId) {
    data.message_ids.forEach((id) => {
      const row = document.querySelector(`.msg-row[data-message-id="${id}"] .msg-meta`);
      if (row) row.textContent = row.textContent.replace(/Sent|Delivered/, "Seen");
    });
  }
});

// ---------------------------------------------------------------------------
// Chat actions
// ---------------------------------------------------------------------------

document.getElementById("btnCloseChat").addEventListener("click", async () => {
  if (!currentChatId) return;
  await fetch(`/admin/api/chats/${currentChatId}/close`, { method: "POST" });
  loadConversations();
});
document.getElementById("btnArchiveChat").addEventListener("click", async () => {
  if (!currentChatId) return;
  await fetch(`/admin/api/chats/${currentChatId}/archive`, { method: "POST" });
  loadConversations();
});
document.getElementById("btnBlockVisitor").addEventListener("click", async () => {
  if (!currentChatId) return;
  if (!confirm("Block this visitor? They will not be able to send messages.")) return;
  await fetch(`/admin/api/chats/${currentChatId}/block`, { method: "POST" });
});
document.getElementById("btnExportCsv").addEventListener("click", () => {
  if (!currentChatId) return;
  window.open(`/admin/api/chats/${currentChatId}/export/csv`, "_blank");
});
document.getElementById("btnExportPdf").addEventListener("click", () => {
  if (!currentChatId) return;
  window.open(`/admin/api/chats/${currentChatId}/export/pdf`, "_blank");
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
function escapeAttr(str) {
  return (str || "").replace(/"/g, "&quot;");
}
function debounce(fn, delay) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

preload().then(() => {
  loadConversations();
  setInterval(loadConversations, 15000);
});
