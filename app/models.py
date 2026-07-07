import json
import secrets
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


def utcnow():
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Roles & Permissions
# ---------------------------------------------------------------------------

ALL_PERMISSIONS = [
    "dashboard.view",
    "inbox.view",
    "inbox.reply",
    "inbox.assign",
    "inbox.close",
    "inbox.delete",
    "visitors.view",
    "visitors.manage",
    "settings.manage",
    "faq.manage",
    "canned.manage",
    "admins.manage",
    "automation.manage",
]

DEFAULT_ROLE_PERMISSIONS = {
    "Owner": ALL_PERMISSIONS,
    "Admin": [p for p in ALL_PERMISSIONS if p != "admins.manage"],
    "Manager": [
        "dashboard.view", "inbox.view", "inbox.reply", "inbox.assign",
        "inbox.close", "visitors.view", "visitors.manage", "faq.manage",
        "canned.manage",
    ],
    "Support Agent": [
        "dashboard.view", "inbox.view", "inbox.reply", "visitors.view",
    ],
}


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    permissions = db.Column(db.Text, default="[]")  # JSON list of permission strings

    admins = db.relationship("Admin", backref="role", lazy=True)

    def get_permissions(self):
        try:
            return json.loads(self.permissions or "[]")
        except (ValueError, TypeError):
            return []

    def set_permissions(self, perms):
        self.permissions = json.dumps(perms)

    def has_permission(self, perm):
        return perm in self.get_permissions()


# ---------------------------------------------------------------------------
# Admin (staff user)
# ---------------------------------------------------------------------------

class Admin(UserMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    is_active_agent = db.Column(db.Boolean, default=True)
    is_online = db.Column(db.Boolean, default=False)
    avatar = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    assigned_chats = db.relationship("Chat", backref="assigned_admin", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, perm):
        return self.role.has_permission(perm) if self.role else False


# ---------------------------------------------------------------------------
# Visitor & Sessions
# ---------------------------------------------------------------------------

class Visitor(db.Model):
    __tablename__ = "visitors"

    id = db.Column(db.Integer, primary_key=True)
    visitor_uid = db.Column(db.String(20), unique=True, nullable=False)

    name = db.Column(db.String(120), nullable=True)
    mobile = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    company = db.Column(db.String(120), nullable=True)
    info_captured = db.Column(db.Boolean, default=False)  # asked once, never again

    tags = db.Column(db.Text, default="[]")  # JSON list e.g. ["VIP", "Returning"]
    is_vip = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)
    lead_score = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text, default="")

    ip_address = db.Column(db.String(64), nullable=True)
    country = db.Column(db.String(80), nullable=True)
    city = db.Column(db.String(80), nullable=True)
    browser = db.Column(db.String(80), nullable=True)
    os = db.Column(db.String(80), nullable=True)
    device = db.Column(db.String(40), nullable=True)
    language = db.Column(db.String(20), nullable=True)
    current_page = db.Column(db.String(500), nullable=True)

    is_online = db.Column(db.Boolean, default=False)
    first_seen = db.Column(db.DateTime, default=utcnow)
    last_seen = db.Column(db.DateTime, default=utcnow)
    visit_count = db.Column(db.Integer, default=1)

    chats = db.relationship("Chat", backref="visitor", lazy=True)
    sessions = db.relationship("VisitorSession", backref="visitor", lazy=True)

    def get_tags(self):
        try:
            return json.loads(self.tags or "[]")
        except (ValueError, TypeError):
            return []

    def set_tags(self, tags_list):
        self.tags = json.dumps(tags_list)

    @staticmethod
    def generate_uid():
        return "VIS-" + secrets.token_hex(3).upper()


class VisitorSession(db.Model):
    __tablename__ = "visitor_sessions"

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    page = db.Column(db.String(500), nullable=True)
    time_spent_seconds = db.Column(db.Integer, default=0)


# ---------------------------------------------------------------------------
# Chat & Messages
# ---------------------------------------------------------------------------

class Chat(db.Model):
    __tablename__ = "chats"

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id"), nullable=False)
    assigned_admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=True)

    status = db.Column(db.String(20), default="open")  # open, closed, archived
    is_blocked = db.Column(db.Boolean, default=False)

    unread_count = db.Column(db.Integer, default=0)  # unread by admin
    visitor_unread_count = db.Column(db.Integer, default=0)  # unread by visitor

    created_at = db.Column(db.DateTime, default=utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    last_message_at = db.Column(db.DateTime, default=utcnow)

    messages = db.relationship(
        "Message", backref="chat", lazy=True, order_by="Message.created_at",
        cascade="all, delete-orphan",
    )


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chats.id"), nullable=False)

    sender_type = db.Column(db.String(20), nullable=False)  # visitor, admin, bot, system
    sender_id = db.Column(db.Integer, nullable=True)  # admin id if sender_type == admin
    sender_name = db.Column(db.String(120), nullable=True)

    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default="text")  # text, system, quick_reply

    status = db.Column(db.String(20), default="sent")  # sent, delivered, seen
    reply_to_id = db.Column(db.Integer, db.ForeignKey("messages.id"), nullable=True)
    is_pinned = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    reactions = db.Column(db.Text, default="{}")  # JSON {"👍": ["admin:1"], ...}

    created_at = db.Column(db.DateTime, default=utcnow)

    reply_to = db.relationship("Message", remote_side=[id])

    def get_reactions(self):
        try:
            return json.loads(self.reactions or "{}")
        except (ValueError, TypeError):
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "sender_type": self.sender_type,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "content": "" if self.is_deleted else self.content,
            "message_type": self.message_type,
            "status": self.status,
            "reply_to_id": self.reply_to_id,
            "is_pinned": self.is_pinned,
            "is_deleted": self.is_deleted,
            "reactions": self.get_reactions(),
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=True)  # null = broadcast
    chat_id = db.Column(db.Integer, db.ForeignKey("chats.id"), nullable=True)
    text = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Settings (key-value store)
# ---------------------------------------------------------------------------

class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=None):
        row = Setting.query.get(key)
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = Setting.query.get(key)
        if row:
            row.value = value
        else:
            row = Setting(key=key, value=value)
            db.session.add(row)


DEFAULT_SETTINGS = {
    "business_name": "Kapoore Art",
    "logo_url": "",
    "favicon_url": "",
    "theme_color": "#4f46e5",
    "widget_color": "#4f46e5",
    "widget_position": "bottom-right",
    "border_radius": "16",
    "greeting_message": "Hello 👋 Welcome to Kapoore Art. How can we help you today?",
    "offline_message": "Hello 👋 Our support team is currently offline. Leave your message, we will reply shortly.",
    "whatsapp_number": "",
    "support_email": "",
    "support_phone": "",
    "timezone": "Asia/Kolkata",
    "language": "en",
    "api_key": "demo-api-key-123",
    "dark_mode_default": "false",
    "auto_close_minutes": "1440",
    "typing_delay_ms": "1200",
}


# ---------------------------------------------------------------------------
# Business Hours
# ---------------------------------------------------------------------------

class BusinessHours(db.Model):
    __tablename__ = "business_hours"

    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday ... 6=Sunday
    open_time = db.Column(db.String(5), default="09:00")
    close_time = db.Column(db.String(5), default="18:00")
    is_closed = db.Column(db.Boolean, default=False)


# ---------------------------------------------------------------------------
# FAQ
# ---------------------------------------------------------------------------

class FAQ(db.Model):
    __tablename__ = "faqs"

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), default="General")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)


# ---------------------------------------------------------------------------
# Canned Replies
# ---------------------------------------------------------------------------

class CannedReply(db.Model):
    __tablename__ = "canned_replies"

    id = db.Column(db.Integer, primary_key=True)
    shortcut = db.Column(db.String(50), unique=True, nullable=False)  # e.g. "/price"
    message = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=True)


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

class Log(db.Model):
    __tablename__ = "logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow)
