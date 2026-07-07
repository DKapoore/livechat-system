# Live Chat System — Floating Widget + Admin Panel (No WhatsApp API)

A self-hosted, real-time customer support chat platform: a floating widget you embed
on any website with one `<script>` tag, plus a full admin panel to manage
conversations, visitors, FAQs, canned replies, automation, and team roles.

WhatsApp is **only** used as an optional fallback link shown to visitors when your
team is offline — the core system does not depend on the WhatsApp Business API.

---

## 1. Features

- **Floating widget**: bottom-right (or left) launcher, unread badge, online dot,
  pulse animation, tooltip, smooth open animation, dark mode, mobile full-screen.
- **Welcome screen** with FAQ quick-reply buttons that auto-answer instantly.
- **Visitor identification** (name/mobile/email/company) asked once, skippable,
  remembered via a generated Visitor ID (`VIS-XXXXXX`) stored in `localStorage`.
- **Real-time messaging** over Socket.IO: typing indicators, sent/delivered/seen
  receipts, timestamps, auto-scroll, unlimited history.
- **Smart offline auto-reply** based on configurable Business Hours, with a
  "Continue on WhatsApp" button that hands off the conversation.
- **Admin panel**: Messenger-style inbox (conversation list + live chat + visitor
  detail panel), dashboard with 30-day chart and live stats, visitor management
  (search/filter/tag/VIP/block/export), FAQ builder, canned-reply shortcuts
  (`/price`, `/design`, …), business-hours scheduler, and role-based team
  management (Owner / Admin / Manager / Support Agent).
- **Security**: hashed passwords (Werkzeug), CSRF-safe forms, input sanitization,
  session timeout, permission checks on every admin route and API endpoint.
- **Exports**: chat transcript to CSV/PDF, visitor list to Excel.

> **Note on scope**: this build is text-first (no file/image/voice attachments
> yet) per the current requirements. The `Message` and `Chat` models are already
> structured so attachments, message reactions, pinning, and search can be
> extended without a schema rewrite — see `app/models.py`.

---

## 2. Project Structure

```
livechat-system/
├── app/
│   ├── __init__.py           # App factory, blueprint registration
│   ├── extensions.py         # db, login_manager, socketio singletons
│   ├── models.py             # All SQLAlchemy models
│   ├── utils.py               # UA parsing, business-hours check, sanitization
│   ├── decorators.py          # @permission_required(...)
│   ├── sockets.py              # All Socket.IO event handlers
│   ├── auth/                   # /admin/login, /admin/logout
│   ├── admin/                  # Dashboard, inbox, visitors, settings, FAQ, etc. + JSON API
│   ├── widget/                  # Public widget REST API (config/session/identify/history)
│   ├── templates/admin/         # Jinja templates for the admin panel
│   └── static/
│       ├── admin/               # Admin panel CSS/JS
│       ├── widget/widget.js      # The embeddable widget (single file)
│       └── uploads/
├── config.py
├── run.py                       # Entry point (Flask-SocketIO server)
├── seed.py                      # Creates tables + default admin/roles/settings
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 3. Local Installation

**Requirements**: Python 3.10+

```bash
cd livechat-system
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # edit SECRET_KEY etc. if you like

python seed.py                   # creates the SQLite DB + default admin
python run.py
```

The server starts at **http://localhost:5000**

- Admin panel: http://localhost:5000/admin/login
  - Email: `owner@example.com`
  - Password: `Owner@123`
  - **Change this password immediately** via Admins & Roles → or add a
    "change password" flow before going to production.
- Demo page with the widget already embedded: http://localhost:5000/demo
- Widget script (for embedding anywhere): `http://localhost:5000/widget.js`

---

## 4. Embedding the widget on any website

Copy the exact snippet shown on the **Settings** page (it includes your live
API key), or use this template:

```html
<script src="https://yourdomain.com/widget.js"></script>
<script>
  LiveChat.init({ apiKey: "YOUR_API_KEY" });
</script>
```

Paste it just before `</body>` on any site — WordPress, Shopify, plain HTML,
React, whatever. No other integration is required.

---

## 5. Configuring the business

Everything below is editable from the admin panel — no code changes needed:

| Where | What you control |
|---|---|
| **Settings** | Business name/logo, theme & widget colors, widget position (left/right), border radius, greeting & offline messages, WhatsApp fallback number, API key, auto-close timer |
| **Business Hours** | Per-day open/close time or "closed all day" — drives the offline auto-reply |
| **FAQ** | Question/answer pairs shown as quick-reply buttons in the welcome screen |
| **Canned Replies** | `/shortcut` → full message, autocompletes while agents type in the inbox |
| **Admins & Roles** | Add team members, assign Owner/Admin/Manager/Support Agent roles |

---

## 6. Roles & permissions

| Role | Access |
|---|---|
| **Owner** | Everything, including managing other admins |
| **Admin** | Everything except managing admins |
| **Manager** | Inbox, visitors, FAQ, canned replies |
| **Support Agent** | Inbox (view + reply) and visitors (view only) |

Permissions are enforced server-side on every route via `@permission_required(...)`
(see `app/decorators.py` and `DEFAULT_ROLE_PERMISSIONS` in `app/models.py`), so
UI links alone are never the only protection.

---

## 7. Deployment

### Docker (recommended)

```bash
docker compose up --build -d
```

The container runs `seed.py` then `run.py` automatically. Data persists in the
mounted `./instance` folder (SQLite file) — swap `DATABASE_URL` in
`docker-compose.yml` for a managed Postgres/MySQL URL to scale beyond SQLite.

### Render

1. Push this repo to GitHub.
2. New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt && python seed.py`
4. Start command: `python run.py`
5. Add environment variables from `.env.example` (set a strong `SECRET_KEY`).
6. Because this app uses Socket.IO with the `threading` async mode, no extra
   worker configuration is required for small/medium traffic. For heavier load,
   switch `SOCKETIO_ASYNC_MODE` to `eventlet` and add `eventlet` to
   `requirements.txt`, then run via `gunicorn -k eventlet -w 1 run:app`.

### VPS (Ubuntu/Debian example)

```bash
sudo apt install python3-venv nginx
git clone <your-repo> && cd livechat-system
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py
# Run with a process manager:
pip install gunicorn eventlet
gunicorn -k eventlet -w 1 -b 127.0.0.1:5000 run:app
```

Then reverse-proxy `yourdomain.com` → `127.0.0.1:5000` with Nginx, and add a
`location /socket.io/` block with `proxy_http_version 1.1` +
`Upgrade`/`Connection` headers so WebSocket upgrades pass through.

---

## 8. Upgrading from SQLite to MySQL/PostgreSQL

Just change `DATABASE_URL`:

```
# PostgreSQL
DATABASE_URL=postgresql://user:password@host:5432/livechat

# MySQL
DATABASE_URL=mysql+pymysql://user:password@host:3306/livechat
```

Install the matching driver (`psycopg2-binary` or `pymysql`), then re-run
`python seed.py` against the new database.

---

## 9. Security notes before going to production

- Change `SECRET_KEY` and the default Owner password immediately.
- Serve behind HTTPS (required for `Notification`/desktop notifications and for
  Secure cookies in real deployments).
- Set `SESSION_COOKIE_SECURE = True` in `config.py` once you're on HTTPS.
- Rotate the widget `api_key` per client if you extend this to multi-tenant SaaS
  (see note below).
- Add a rate limiter (e.g. `Flask-Limiter`) in front of `/widget/api/*` if you
  expect abuse/spam traffic.

## 10. Extending to true multi-tenant SaaS

This build ships **single-tenant** (one business, one API key) to keep the
codebase approachable. To serve multiple client websites from one deployment:

1. Add a `Client` model (id, name, api_key, plan, owner_admin_id).
2. Add `client_id` foreign keys to `Visitor`, `Chat`, `Setting`, `FAQ`, `CannedReply`.
3. Resolve the current client from `apiKey` in `app/widget/routes.py` and scope
   every query by `client_id`.
4. Scope the admin panel's queries by the logged-in admin's `client_id`.

The models and route structure are already organized to make this a additive
change rather than a rewrite.
