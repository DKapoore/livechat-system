from datetime import datetime

from flask import current_app, jsonify, request

from app.extensions import db
from app.models import (
    BusinessHours, Chat, FAQ, Message, Setting, Visitor, VisitorSession,
)
from app.utils import is_within_business_hours, parse_user_agent, sanitize_text
from app.widget import widget_bp


def _check_api_key():
    api_key = request.args.get("apiKey") or request.headers.get("X-Api-Key")
    expected = Setting.get("api_key", current_app.config["DEFAULT_API_KEY"])
    return api_key == expected


@widget_bp.route("/api/config", methods=["GET"])
def config():
    if not _check_api_key():
        return jsonify({"error": "Invalid API key"}), 401

    hours = BusinessHours.query.all()
    online = is_within_business_hours(hours)

    faqs = (
        FAQ.query.filter_by(is_active=True)
        .order_by(FAQ.sort_order.asc())
        .limit(8)
        .all()
    )

    return jsonify({
        "business_name": Setting.get("business_name", "Support"),
        "logo_url": Setting.get("logo_url", ""),
        "theme_color": Setting.get("theme_color", "#4f46e5"),
        "widget_color": Setting.get("widget_color", "#4f46e5"),
        "widget_position": Setting.get("widget_position", "bottom-right"),
        "border_radius": Setting.get("border_radius", "16"),
        "greeting_message": Setting.get("greeting_message", "Hello! How can we help?"),
        "offline_message": Setting.get("offline_message", "We're offline right now."),
        "whatsapp_number": Setting.get("whatsapp_number", ""),
        "is_online": online,
        "faqs": [{"id": f.id, "question": f.question, "category": f.category} for f in faqs],
    })


@widget_bp.route("/api/session", methods=["POST"])
def session():
    """Create or resume a visitor session. Client sends existing visitor_uid
    (from localStorage) if present."""
    if not _check_api_key():
        return jsonify({"error": "Invalid API key"}), 401

    data = request.get_json(silent=True) or {}
    visitor_uid = sanitize_text(data.get("visitor_uid"), 30)
    page = sanitize_text(data.get("page"), 500)
    ua = request.headers.get("User-Agent", "")
    parsed = parse_user_agent(ua)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""

    visitor = Visitor.query.filter_by(visitor_uid=visitor_uid).first() if visitor_uid else None
    is_returning = visitor is not None

    if visitor is None:
        visitor = Visitor(
            visitor_uid=Visitor.generate_uid(),
            ip_address=ip,
            browser=parsed["browser"],
            os=parsed["os"],
            device=parsed["device"],
            language=request.headers.get("Accept-Language", "")[:20],
            current_page=page,
        )
        db.session.add(visitor)
    else:
        visitor.visit_count = (visitor.visit_count or 1) + 1
        visitor.ip_address = ip
        visitor.browser = parsed["browser"]
        visitor.os = parsed["os"]
        visitor.device = parsed["device"]
        visitor.current_page = page
        visitor.last_seen = datetime.utcnow()

    visitor.is_online = True
    db.session.flush()

    vsession = VisitorSession(visitor_id=visitor.id, ip_address=ip, page=page)
    db.session.add(vsession)

    if visitor.is_blocked:
        db.session.commit()
        return jsonify({"error": "blocked"}), 403

    # Find or create an open chat for this visitor
    chat = (
        Chat.query.filter_by(visitor_id=visitor.id)
        .filter(Chat.status != "archived")
        .order_by(Chat.created_at.desc())
        .first()
    )
    if chat is None:
        chat = Chat(visitor_id=visitor.id, status="open")
        db.session.add(chat)
        db.session.flush()

    db.session.commit()

    history = [m.to_dict() for m in chat.messages]

    return jsonify({
        "visitor_uid": visitor.visitor_uid,
        "chat_id": chat.id,
        "is_returning": is_returning,
        "needs_identification": not visitor.info_captured,
        "history": history,
    })


@widget_bp.route("/api/identify", methods=["POST"])
def identify():
    if not _check_api_key():
        return jsonify({"error": "Invalid API key"}), 401

    data = request.get_json(silent=True) or {}
    visitor_uid = sanitize_text(data.get("visitor_uid"), 30)
    visitor = Visitor.query.filter_by(visitor_uid=visitor_uid).first()
    if not visitor:
        return jsonify({"error": "Visitor not found"}), 404

    visitor.name = sanitize_text(data.get("name"), 120) or visitor.name
    visitor.mobile = sanitize_text(data.get("mobile"), 30) or visitor.mobile
    visitor.email = sanitize_text(data.get("email"), 120) or visitor.email
    visitor.company = sanitize_text(data.get("company"), 120) or visitor.company
    visitor.info_captured = True
    db.session.commit()

    return jsonify({"success": True})


@widget_bp.route("/api/history/<visitor_uid>", methods=["GET"])
def history(visitor_uid):
    if not _check_api_key():
        return jsonify({"error": "Invalid API key"}), 401

    visitor = Visitor.query.filter_by(visitor_uid=sanitize_text(visitor_uid, 30)).first()
    if not visitor:
        return jsonify({"messages": []})

    chat = (
        Chat.query.filter_by(visitor_id=visitor.id)
        .order_by(Chat.created_at.desc())
        .first()
    )
    if not chat:
        return jsonify({"messages": []})

    return jsonify({"messages": [m.to_dict() for m in chat.messages]})
