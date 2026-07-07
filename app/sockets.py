from datetime import datetime

from flask import request
from flask_login import current_user
from flask_socketio import join_room, emit

from app.extensions import db, socketio
from app.models import (
    BusinessHours, Chat, FAQ, Message, Notification, Setting, Visitor,
)
from app.utils import is_within_business_hours, sanitize_text

ADMIN_ROOM = "admins"


def _chat_room(chat_id):
    return f"chat_{chat_id}"


def _broadcast_to_admins(event, payload):
    socketio.emit(event, payload, room=ADMIN_ROOM)


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------

@socketio.on("connect")
def handle_connect():
    emit("connected", {"sid": request.sid})


@socketio.on("disconnect")
def handle_disconnect():
    pass


@socketio.on("join_visitor_room")
def join_visitor_room(data):
    chat_id = data.get("chat_id")
    if chat_id:
        join_room(_chat_room(chat_id))


@socketio.on("join_admin_room")
def join_admin_room(data):
    # current_user works here because Flask-SocketIO shares the Flask session
    if current_user.is_authenticated:
        join_room(ADMIN_ROOM)
        current_user.is_online = True
        db.session.commit()
        emit("joined_admin_room", {"ok": True})


@socketio.on("join_chat_room")
def join_chat_room(data):
    """Admin opens a specific conversation."""
    chat_id = data.get("chat_id")
    if chat_id and current_user.is_authenticated:
        join_room(_chat_room(chat_id))
        chat = Chat.query.get(chat_id)
        if chat:
            chat.unread_count = 0
            db.session.commit()


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------

@socketio.on("send_message")
def send_message(data):
    chat_id = data.get("chat_id")
    sender_type = data.get("sender_type")  # visitor | admin
    content = sanitize_text(data.get("content"), 5000)
    reply_to_id = data.get("reply_to_id")

    if not chat_id or not content or sender_type not in ("visitor", "admin"):
        emit("error_message", {"error": "Invalid message payload"})
        return

    chat = Chat.query.get(chat_id)
    if not chat or chat.is_blocked:
        emit("error_message", {"error": "Chat not available"})
        return

    sender_id = None
    sender_name = None
    if sender_type == "admin":
        if not current_user.is_authenticated:
            emit("error_message", {"error": "Not authorized"})
            return
        sender_id = current_user.id
        sender_name = current_user.name
    else:
        sender_name = chat.visitor.name or chat.visitor.visitor_uid

    message = Message(
        chat_id=chat.id,
        sender_type=sender_type,
        sender_id=sender_id,
        sender_name=sender_name,
        content=content,
        status="sent",
        reply_to_id=reply_to_id,
    )
    db.session.add(message)

    chat.last_message_at = datetime.utcnow()
    if sender_type == "visitor":
        chat.unread_count = (chat.unread_count or 0) + 1
    else:
        chat.visitor_unread_count = (chat.visitor_unread_count or 0) + 1
        chat.status = "open"

    db.session.commit()

    payload = message.to_dict()
    socketio.emit("new_message", payload, room=_chat_room(chat.id))
    _broadcast_to_admins("inbox_update", {"chat_id": chat.id, "message": payload})

    if sender_type == "visitor":
        _handle_visitor_message_side_effects(chat, content)


def _handle_visitor_message_side_effects(chat, content):
    """Auto offline reply + notification for admins."""
    notif = Notification(chat_id=chat.id, text=f"New message from {chat.visitor.name or chat.visitor.visitor_uid}")
    db.session.add(notif)
    db.session.commit()
    _broadcast_to_admins("notification", {
        "chat_id": chat.id, "text": notif.text, "created_at": notif.created_at.isoformat(),
    })

    # Only trigger auto offline reply once per chat (no admin reply yet)
    admin_replied = any(m.sender_type == "admin" for m in chat.messages)
    already_auto_replied = any(
        m.sender_type == "bot" and "offline" in (m.message_type or "") for m in chat.messages
    )
    if admin_replied or already_auto_replied:
        return

    hours = BusinessHours.query.all()
    if is_within_business_hours(hours):
        return

    offline_msg = Setting.get("offline_message", "We're offline right now. Leave a message!")
    bot_message = Message(
        chat_id=chat.id, sender_type="bot", sender_name="Auto-Reply",
        content=offline_msg, message_type="system_offline", status="sent",
    )
    db.session.add(bot_message)
    db.session.commit()
    socketio.emit("new_message", bot_message.to_dict(), room=_chat_room(chat.id))


@socketio.on("quick_reply")
def quick_reply(data):
    """Visitor clicked a welcome-screen quick button or FAQ button."""
    chat_id = data.get("chat_id")
    faq_id = data.get("faq_id")
    label = sanitize_text(data.get("label"), 200)

    chat = Chat.query.get(chat_id)
    if not chat:
        return

    visitor_msg = Message(
        chat_id=chat.id, sender_type="visitor", sender_name=chat.visitor.name or chat.visitor.visitor_uid,
        content=label, message_type="quick_reply", status="sent",
    )
    db.session.add(visitor_msg)
    chat.last_message_at = datetime.utcnow()
    chat.unread_count = (chat.unread_count or 0) + 1
    db.session.commit()
    socketio.emit("new_message", visitor_msg.to_dict(), room=_chat_room(chat.id))
    _broadcast_to_admins("inbox_update", {"chat_id": chat.id, "message": visitor_msg.to_dict()})

    faq = FAQ.query.get(faq_id) if faq_id else None
    if faq:
        bot_msg = Message(
            chat_id=chat.id, sender_type="bot", sender_name="Auto-Reply",
            content=faq.answer, message_type="text", status="sent",
        )
        db.session.add(bot_msg)
        db.session.commit()
        socketio.emit("new_message", bot_msg.to_dict(), room=_chat_room(chat.id))
    else:
        _handle_visitor_message_side_effects(chat, label)


@socketio.on("typing")
def typing(data):
    chat_id = data.get("chat_id")
    sender_type = data.get("sender_type")
    is_typing = bool(data.get("is_typing"))
    if not chat_id:
        return
    socketio.emit(
        "typing_status",
        {"chat_id": chat_id, "sender_type": sender_type, "is_typing": is_typing},
        room=_chat_room(chat_id),
        include_self=False,
    )
    if sender_type == "admin":
        _broadcast_to_admins("typing_status_inbox", {"chat_id": chat_id, "is_typing": is_typing})


@socketio.on("message_seen")
def message_seen(data):
    chat_id = data.get("chat_id")
    seen_by = data.get("sender_type")  # who is marking as seen
    chat = Chat.query.get(chat_id)
    if not chat:
        return

    target_sender = "visitor" if seen_by == "admin" else "admin"
    updated_ids = []
    for m in chat.messages:
        if m.sender_type == target_sender and m.status != "seen":
            m.status = "seen"
            updated_ids.append(m.id)
    if seen_by == "admin":
        chat.unread_count = 0
    else:
        chat.visitor_unread_count = 0
    db.session.commit()

    if updated_ids:
        socketio.emit(
            "messages_seen", {"chat_id": chat_id, "message_ids": updated_ids},
            room=_chat_room(chat_id),
        )


@socketio.on("react_message")
def react_message(data):
    message_id = data.get("message_id")
    emoji = sanitize_text(data.get("emoji"), 10)
    actor = sanitize_text(data.get("actor"), 60)  # e.g. "admin:3" or "visitor:VIS-XXX"

    message = Message.query.get(message_id)
    if not message or not emoji:
        return
    reactions = message.get_reactions()
    actors = reactions.setdefault(emoji, [])
    if actor in actors:
        actors.remove(actor)
        if not actors:
            del reactions[emoji]
    else:
        actors.append(actor)
    message.reactions = __import__("json").dumps(reactions)
    db.session.commit()
    socketio.emit(
        "message_reaction_updated",
        {"message_id": message_id, "reactions": reactions},
        room=_chat_room(message.chat_id),
    )


@socketio.on("pin_message")
def pin_message(data):
    if not current_user.is_authenticated:
        return
    message_id = data.get("message_id")
    pinned = bool(data.get("pinned"))
    message = Message.query.get(message_id)
    if not message:
        return
    message.is_pinned = pinned
    db.session.commit()
    socketio.emit(
        "message_pin_updated", {"message_id": message_id, "is_pinned": pinned},
        room=_chat_room(message.chat_id),
    )
