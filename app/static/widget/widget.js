/* Live Chat Widget — embeddable, framework-free.
 * Usage:
 *   <script src="https://yourdomain.com/widget.js"></script>
 *   <script>LiveChat.init({ apiKey: "CLIENT_API_KEY", serverUrl: "" });</script>
 */
(function () {
  "use strict";

  const STORAGE_KEY = "lc_visitor_uid";
  const STORAGE_INFO_KEY = "lc_info_captured";

  const LiveChat = {
    _cfg: null,
    _socket: null,
    _chatId: null,
    _visitorUid: null,
    _open: false,
    _cfgData: null,
    _typingTimer: null,

    init(userCfg) {
      this._cfg = Object.assign({
        apiKey: "",
        serverUrl: (function () {
          const s = document.currentScript || [...document.scripts].find((s) => s.src && s.src.includes("widget.js"));
          if (s) { try { return new URL(s.src).origin; } catch (e) {} }
          return "";
        })(),
      }, userCfg || {});

      this._visitorUid = localStorage.getItem(STORAGE_KEY) || null;

      this._loadSocketIoThen(() => {
        this._fetchConfig().then((cfgData) => {
          this._cfgData = cfgData;
          this._injectStyles(cfgData);
          this._buildDom(cfgData);
          this._startSession();
        });
      });
    },

    // -------------------------------------------------------------------
    // Bootstrapping
    // -------------------------------------------------------------------

    _loadSocketIoThen(cb) {
      if (window.io) return cb();
      const script = document.createElement("script");
      script.src = "https://cdn.socket.io/4.7.5/socket.io.min.js";
      script.onload = cb;
      document.head.appendChild(script);
    },

    async _fetchConfig() {
      const res = await fetch(`${this._cfg.serverUrl}/widget/api/config?apiKey=${encodeURIComponent(this._cfg.apiKey)}`);
      if (!res.ok) {
        console.error("LiveChat: invalid API key or server unreachable");
        return {};
      }
      return res.json();
    },

    // -------------------------------------------------------------------
    // Styles
    // -------------------------------------------------------------------

    _injectStyles(cfg) {
      const radius = (cfg.border_radius || "16") + "px";
      const color = cfg.widget_color || "#4f46e5";
      const position = cfg.widget_position === "bottom-left" ? "left: 20px;" : "right: 20px;";

      const style = document.createElement("style");
      style.textContent = `
        #lc-widget-root * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        #lc-widget-root { position: fixed; bottom: 20px; ${position} z-index: 999999; }
        #lc-toggle-btn {
          width: 62px; height: 62px; border-radius: 50%; background: ${color}; border: none;
          box-shadow: 0 8px 24px rgba(0,0,0,.2); cursor: pointer; display:flex; align-items:center; justify-content:center;
          position: relative; transition: transform .25s ease;
        }
        #lc-toggle-btn:hover { transform: scale(1.06); }
        #lc-toggle-btn svg { width: 28px; height: 28px; fill: #fff; }
        #lc-toggle-btn .lc-pulse {
          position:absolute; inset:0; border-radius:50%; background:${color}; opacity:.55;
          animation: lc-pulse 2.2s ease-out infinite;
        }
        @keyframes lc-pulse { 0% { transform: scale(1); opacity:.55;} 100% { transform: scale(1.6); opacity:0; } }
        #lc-unread-badge {
          position:absolute; top:-4px; right:-4px; background:#ef4444; color:#fff; font-size:11px; font-weight:700;
          min-width:20px; height:20px; border-radius:50%; display:flex; align-items:center; justify-content:center; padding:0 4px;
        }
        #lc-online-dot {
          position:absolute; bottom:2px; right:2px; width:12px; height:12px; border-radius:50%;
          background:#22c55e; border:2px solid #fff;
        }
        #lc-tooltip {
          position:absolute; bottom: 74px; ${position.includes("left") ? "left:0;" : "right:0;"}
          background:#111827; color:#fff; padding:8px 14px; border-radius: 10px; font-size:13px; white-space:nowrap;
          box-shadow:0 6px 16px rgba(0,0,0,.2); opacity:0; transform: translateY(6px); pointer-events:none;
          transition: all .25s ease;
        }
        #lc-toggle-btn:hover ~ #lc-tooltip, #lc-toggle-wrap:hover #lc-tooltip { opacity:1; transform: translateY(0); }

        #lc-chat-window {
          position: fixed; bottom: 96px; ${position}
          width: 380px; height: 550px; max-height: 80vh;
          background: var(--lc-bg, #fff); border-radius: ${radius}; box-shadow: 0 16px 48px rgba(0,0,0,.25);
          display:flex; flex-direction:column; overflow:hidden;
          opacity:0; transform: translateY(24px) scale(.96); pointer-events:none; transition: all .28s cubic-bezier(.2,.8,.2,1);
        }
        #lc-chat-window.lc-visible { opacity:1; transform: translateY(0) scale(1); pointer-events:all; }
        @media (max-width: 480px) {
          #lc-chat-window { width: 100vw; height: 100vh; max-height: 100vh; bottom:0; right:0; left:0; border-radius:0; }
        }

        #lc-chat-window[data-theme="dark"] { --lc-bg:#151824; --lc-text:#eef0f6; --lc-border:#2a2e3d; --lc-bubble:#232838; }
        #lc-chat-window { --lc-text:#1a1d29; --lc-border:#e5e9f2; --lc-bubble:#f4f6fb; color: var(--lc-text); }

        #lc-header { background: ${color}; color:#fff; padding: 14px 16px; display:flex; align-items:center; justify-content:space-between; }
        #lc-header-info { display:flex; align-items:center; gap:10px; }
        #lc-header-logo { width:34px; height:34px; border-radius:50%; background:rgba(255,255,255,.2); display:flex; align-items:center; justify-content:center; font-weight:700; overflow:hidden; }
        #lc-header-logo img { width:100%; height:100%; object-fit:cover; }
        #lc-header-name { font-weight:700; font-size:14.5px; }
        #lc-header-status { font-size:11.5px; opacity:.9; }
        #lc-header-actions { display:flex; gap:6px; }
        #lc-header-actions button { background: rgba(255,255,255,.15); border:none; color:#fff; width:28px; height:28px; border-radius:8px; cursor:pointer; font-size:14px; }
        #lc-header-actions button:hover { background: rgba(255,255,255,.28); }

        #lc-body { flex:1; overflow-y:auto; padding: 14px; background: var(--lc-bg); }
        #lc-welcome { text-align:left; }
        #lc-welcome-msg { background: var(--lc-bubble); border-radius: 14px; padding: 12px 14px; font-size: 14px; margin-bottom: 12px; }
        .lc-quick-btns { display:flex; flex-wrap:wrap; gap:8px; margin-bottom: 16px; }
        .lc-quick-btn { background: #fff; border: 1.5px solid ${color}; color:${color}; padding: 7px 12px; border-radius: 20px; font-size:12.5px; cursor:pointer; }
        .lc-quick-btn:hover { background:${color}; color:#fff; }

        .lc-msg-row { display:flex; flex-direction:column; margin-bottom:10px; max-width:80%; }
        .lc-msg-row.lc-from-visitor { align-self:flex-end; margin-left:auto; align-items:flex-end; }
        .lc-msg-row.lc-from-admin, .lc-msg-row.lc-from-bot { align-self:flex-start; align-items:flex-start; }
        .lc-bubble { padding: 9px 13px; border-radius:14px; font-size:13.5px; line-height:1.4; word-wrap:break-word; }
        .lc-from-visitor .lc-bubble { background:${color}; color:#fff; border-bottom-right-radius:4px; }
        .lc-from-admin .lc-bubble { background: var(--lc-bubble); border-bottom-left-radius:4px; }
        .lc-from-bot .lc-bubble { background:#fef3c7; color:#92400e; border-bottom-left-radius:4px; }
        .lc-msg-meta { font-size:10.5px; color:#9aa1b1; margin-top:3px; }
        .lc-whatsapp-btn { display:inline-block; margin-top:8px; background:#25D366; color:#fff; padding:7px 14px; border-radius:20px; font-size:12.5px; text-decoration:none; }

        #lc-typing { font-size:12px; color:#9aa1b1; padding: 0 14px 6px; font-style:italic; }

        #lc-identify-form { padding: 14px; border-top:1px solid var(--lc-border); }
        #lc-identify-form input { width:100%; padding:9px 12px; margin-bottom:8px; border-radius:10px; border:1px solid var(--lc-border); background: var(--lc-bg); color: var(--lc-text); font-size:13px; }
        #lc-identify-form .lc-row { display:flex; gap:8px; }
        #lc-identify-form button.lc-submit { background:${color}; color:#fff; border:none; padding:9px 14px; border-radius:10px; cursor:pointer; font-weight:600; font-size:13px; flex:1; }
        #lc-identify-form button.lc-skip { background: var(--lc-bubble); color: var(--lc-text); border:none; padding:9px 14px; border-radius:10px; cursor:pointer; font-size:13px; }

        #lc-composer { padding: 10px 12px; border-top:1px solid var(--lc-border); display:flex; gap:8px; align-items:center; }
        #lc-input { flex:1; padding:10px 14px; border-radius:20px; border:1px solid var(--lc-border); background: var(--lc-bg); color: var(--lc-text); font-size:13.5px; }
        #lc-send-btn { background:${color}; border:none; color:#fff; width:38px; height:38px; border-radius:50%; cursor:pointer; display:flex; align-items:center; justify-content:center; }
        #lc-send-btn svg { width:16px; height:16px; fill:#fff; }
      `;
      document.head.appendChild(style);
    },

    // -------------------------------------------------------------------
    // DOM construction
    // -------------------------------------------------------------------

    _buildDom(cfg) {
      const root = document.createElement("div");
      root.id = "lc-widget-root";
      root.innerHTML = `
        <div id="lc-toggle-wrap" style="position:relative;">
          <button id="lc-toggle-btn" aria-label="Open chat">
            <span class="lc-pulse"></span>
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.03 2 11c0 2.62 1.28 4.97 3.34 6.63L4 22l4.86-1.6C10.14 20.78 11.55 21 12 21c5.52 0 10-4.03 10-9s-4.48-10-10-10z"/></svg>
            <span id="lc-unread-badge" style="display:none;">0</span>
            <span id="lc-online-dot"></span>
          </button>
          <div id="lc-tooltip">Need help? Chat with us</div>
        </div>

        <div id="lc-chat-window">
          <div id="lc-header">
            <div id="lc-header-info">
              <div id="lc-header-logo">${cfg.logo_url ? `<img src="${cfg.logo_url}">` : (cfg.business_name || "?")[0]}</div>
              <div>
                <div id="lc-header-name">${escapeHtml(cfg.business_name || "Support")}</div>
                <div id="lc-header-status">${cfg.is_online ? "🟢 Typically replies instantly" : "⚪ Currently offline"}</div>
              </div>
            </div>
            <div id="lc-header-actions">
              <button id="lc-dark-toggle" title="Dark mode">🌙</button>
              <button id="lc-minimize-btn" title="Minimize">—</button>
              <button id="lc-close-btn" title="Close">✕</button>
            </div>
          </div>

          <div id="lc-body"></div>
          <div id="lc-typing" style="display:none;">Typing…</div>

          <div id="lc-identify-form" style="display:none;">
            <input type="text" id="lc-f-name" placeholder="Your name">
            <div class="lc-row">
              <input type="text" id="lc-f-mobile" placeholder="Mobile number">
              <input type="email" id="lc-f-email" placeholder="Email (optional)">
            </div>
            <input type="text" id="lc-f-company" placeholder="Company (optional)">
            <div class="lc-row">
              <button class="lc-submit" id="lc-f-submit">Start Chat</button>
              <button class="lc-skip" id="lc-f-skip">Skip</button>
            </div>
          </div>

          <div id="lc-composer">
            <input type="text" id="lc-input" placeholder="Type a message…">
            <button id="lc-send-btn"><svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg></button>
          </div>
        </div>
      `;
      document.body.appendChild(root);

      document.getElementById("lc-toggle-btn").addEventListener("click", () => this._toggleWindow());
      document.getElementById("lc-close-btn").addEventListener("click", () => this._toggleWindow(false));
      document.getElementById("lc-minimize-btn").addEventListener("click", () => this._toggleWindow(false));
      document.getElementById("lc-dark-toggle").addEventListener("click", () => this._toggleDarkMode());
      document.getElementById("lc-send-btn").addEventListener("click", () => this._sendMessage());
      document.getElementById("lc-input").addEventListener("keydown", (e) => { if (e.key === "Enter") this._sendMessage(); });
      document.getElementById("lc-input").addEventListener("input", () => this._notifyTyping());
      document.getElementById("lc-f-submit").addEventListener("click", () => this._submitIdentify());
      document.getElementById("lc-f-skip").addEventListener("click", () => this._hideIdentifyForm());

      if (cfg.dark_mode_default === "true" || cfg.dark_mode_default === true) {
        this._toggleDarkMode(true);
      }
    },

    _toggleWindow(force) {
      const win = document.getElementById("lc-chat-window");
      this._open = force !== undefined ? force : !this._open;
      win.classList.toggle("lc-visible", this._open);
      if (this._open) {
        this._clearUnreadBadge();
        document.getElementById("lc-body").scrollTop = document.getElementById("lc-body").scrollHeight;
      }
    },

    _toggleDarkMode(force) {
      const win = document.getElementById("lc-chat-window");
      const isDark = win.getAttribute("data-theme") === "dark";
      const next = force !== undefined ? force : !isDark;
      if (next) win.setAttribute("data-theme", "dark"); else win.removeAttribute("data-theme");
    },

    // -------------------------------------------------------------------
    // Session
    // -------------------------------------------------------------------

    async _startSession() {
      const res = await fetch(`${this._cfg.serverUrl}/widget/api/session?apiKey=${encodeURIComponent(this._cfg.apiKey)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitor_uid: this._visitorUid, page: location.href }),
      });
      if (!res.ok) return;
      const data = await res.json();

      this._visitorUid = data.visitor_uid;
      this._chatId = data.chat_id;
      localStorage.setItem(STORAGE_KEY, this._visitorUid);

      this._connectSocket();

      if (data.history && data.history.length) {
        data.history.forEach((m) => this._renderMessage(m, false));
      } else {
        this._renderWelcomeScreen();
      }

      if (data.needs_identification) {
        document.getElementById("lc-identify-form").style.display = "block";
      }

      document.getElementById("lc-body").scrollTop = document.getElementById("lc-body").scrollHeight;
    },

    _connectSocket() {
      this._socket = io(this._cfg.serverUrl, { transports: ["websocket", "polling"] });
      this._socket.on("connect", () => {
        this._socket.emit("join_visitor_room", { chat_id: this._chatId });
      });
      this._socket.on("new_message", (msg) => {
        if (msg.chat_id !== this._chatId) return;
        this._renderMessage(msg, true);
        if (!this._open && msg.sender_type !== "visitor") this._incrementUnread();
      });
      this._socket.on("typing_status", (data) => {
        if (data.chat_id === this._chatId && data.sender_type === "admin") {
          document.getElementById("lc-typing").style.display = data.is_typing ? "block" : "none";
        }
      });
    },

    // -------------------------------------------------------------------
    // Welcome screen / quick buttons
    // -------------------------------------------------------------------

    _renderWelcomeScreen() {
      const body = document.getElementById("lc-body");
      const cfg = this._cfgData || {};
      const wrap = document.createElement("div");
      wrap.id = "lc-welcome";
      const faqButtons = (cfg.faqs || [])
        .map((f) => `<button class="lc-quick-btn" data-faq-id="${f.id}" data-label="${escapeAttr(f.question)}">${escapeHtml(f.question)}</button>`)
        .join("");
      wrap.innerHTML = `
        <div id="lc-welcome-msg">${escapeHtml(cfg.greeting_message || "Hello! How can we help you today?")}</div>
        <div class="lc-quick-btns">
          ${faqButtons}
          <button class="lc-quick-btn" data-label="Talk to Support">Talk to Support</button>
        </div>
      `;
      body.appendChild(wrap);
      wrap.querySelectorAll(".lc-quick-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          this._socket.emit("quick_reply", {
            chat_id: this._chatId,
            faq_id: btn.dataset.faqId || null,
            label: btn.dataset.label,
          });
        });
      });
    },

    // -------------------------------------------------------------------
    // Visitor identification
    // -------------------------------------------------------------------

    async _submitIdentify() {
      const name = document.getElementById("lc-f-name").value.trim();
      const mobile = document.getElementById("lc-f-mobile").value.trim();
      const email = document.getElementById("lc-f-email").value.trim();
      const company = document.getElementById("lc-f-company").value.trim();

      await fetch(`${this._cfg.serverUrl}/widget/api/identify?apiKey=${encodeURIComponent(this._cfg.apiKey)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitor_uid: this._visitorUid, name, mobile, email, company }),
      });
      this._hideIdentifyForm();
    },

    _hideIdentifyForm() {
      document.getElementById("lc-identify-form").style.display = "none";
    },

    // -------------------------------------------------------------------
    // Messaging
    // -------------------------------------------------------------------

    _sendMessage() {
      const input = document.getElementById("lc-input");
      const content = input.value.trim();
      if (!content || !this._socket) return;
      this._socket.emit("send_message", { chat_id: this._chatId, sender_type: "visitor", content });
      input.value = "";
    },

    _notifyTyping() {
      if (!this._socket) return;
      this._socket.emit("typing", { chat_id: this._chatId, sender_type: "visitor", is_typing: true });
      clearTimeout(this._typingTimer);
      this._typingTimer = setTimeout(() => {
        this._socket.emit("typing", { chat_id: this._chatId, sender_type: "visitor", is_typing: false });
      }, 1500);
    },

    _renderMessage(m, scroll) {
      const body = document.getElementById("lc-body");
      const row = document.createElement("div");
      row.className = `lc-msg-row lc-from-${m.sender_type}`;
      const time = new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      let extra = "";
      const cfg = this._cfgData || {};
      if (m.message_type === "system_offline" && cfg.whatsapp_number) {
        const waText = encodeURIComponent(`Hi, continuing our chat: ${m.content}`);
        extra = `<br><a class="lc-whatsapp-btn" target="_blank" href="https://wa.me/${cfg.whatsapp_number}?text=${waText}">Continue on WhatsApp</a>`;
      }
      row.innerHTML = `<div class="lc-bubble">${escapeHtml(m.content)}${extra}</div><div class="lc-msg-meta">${time}</div>`;
      body.appendChild(row);
      if (scroll) body.scrollTop = body.scrollHeight;
    },

    _incrementUnread() {
      const badge = document.getElementById("lc-unread-badge");
      const n = (parseInt(badge.textContent, 10) || 0) + 1;
      badge.textContent = n;
      badge.style.display = "flex";
    },
    _clearUnreadBadge() {
      const badge = document.getElementById("lc-unread-badge");
      badge.textContent = "0";
      badge.style.display = "none";
    },
  };

  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
  function escapeAttr(str) {
    return (str || "").replace(/"/g, "&quot;");
  }

  window.LiveChat = LiveChat;
})();
