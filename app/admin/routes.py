import csv
import io
import json
from datetime import datetime, timedelta

from flask import (
    Response, current_app, jsonify, render_template, request, send_file,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.admin import admin_bp
from app.decorators import permission_required
from app.extensions import db
from app.models import (
    Admin, BusinessHours, CannedReply, Chat, FAQ, Log, Message, Role,
    Setting, Visitor, DEFAULT_ROLE_PERMISSIONS, ALL_PERMISSIONS,
)
from app.utils import is_valid_shortcut, sanitize_text

# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@admin_bp.route("/")
@login_required
@permission_required("dashboard.view")
def dashboard():
    return render_template("admin/dashboard.html")


@admin_bp.route("/inbox")
@login_required
@permission_required("inbox.view")
def inbox():
    return render_template("admin/inbox.html")


@admin_bp.route("/visitors")
@login_required
@permission_required("visitors.view")
def visitors_page():
    return render_template("admin/visitors.html")


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@permission_required("settings.manage")
def settings_page():
    if request.method == "POST":
        fields = [
            "business_name", "logo_url", "favicon_url", "theme_color", "widget_color",
            "widget_position", "border_radius", "greeting_message", "offline_message",
            "whatsapp_number", "support_email", "support_phone", "timezone",
            "language", "api_key", "auto_close_minutes", "typing_delay_ms",
        ]
        for field in fields:
            if field in request.form:
                Setting.set(field, sanitize_text(request.form.get(field), 2000))
        Setting.set("dark_mode_default", "true" if request.form.get("dark_mode_default") else "false")
        db.session.add(Log(admin_id=current_user.id, action="update_settings"))
        db.session.commit()

    settings = {s.key: s.value for s in Setting.query.all()}
    return render_template("admin/settings.html", settings=settings)


@admin_bp.route("/faq")
@login_required
@permission_required("faq.manage")
def faq_page():
    faqs = FAQ.query.order_by(FAQ.sort_order.asc()).all()
    return render_template("admin/faq.html", faqs=faqs)


@admin_bp.route("/canned")
@login_required
@permission_required("canned.manage")
def canned_page():
    replies = CannedReply.query.all()
    return render_template("admin/canned.html", replies=replies)


@admin_bp.route("/business-hours")
@login_required
@permission_required("automation.manage")
def business_hours_page():
    rows = {r.day_of_week: r for r in BusinessHours.query.all()}
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return render_template("admin/business_hours.html", rows=rows, days=days)


@admin_bp.route("/admins")
@login_required
@permission_required("admins.manage")
def admins_page():
    admins = Admin.query.all()
    roles = Role.query.all()
    return render_template("admin/admins.html", admins=admins, roles=roles)


# ---------------------------------------------------------------------------
# API: Analytics / Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/api/analytics")
@login_required
@permission_required("dashboard.view")
def api_analytics():
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    today_visitors = Visitor.query.filter(Visitor.first_seen >= today_start).count()
    online_visitors = Visitor.query.filter_by(is_online=True).count()
    offline_visitors = Visitor.query.filter_by(is_online=False).count()
    unread_chats = Chat.query.filter(Chat.unread_count > 0).count()
    total_chats = Chat.query.count()
    active_agents = Admin.query.filter_by(is_online=True).count()

    # crude average response time (minutes) across last 100 closed chats
    closed_chats = Chat.query.filter(Chat.status == "closed").order_by(Chat.closed_at.desc()).limit(100).all()
    response_times = []
    for c in closed_chats:
        msgs = sorted(c.messages, key=lambda m: m.created_at)
        first_visitor = next((m for m in msgs if m.sender_type == "visitor"), None)
        first_admin = next((m for m in msgs if m.sender_type == "admin"), None)
        if first_visitor and first_admin and first_admin.created_at > first_visitor.created_at:
            response_times.append((first_admin.created_at - first_visitor.created_at).total_seconds() / 60)
    avg_response = round(sum(response_times) / len(response_times), 1) if response_times else 0

    # last 30 days chat volume
    labels, counts = [], []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        c = Chat.query.filter(Chat.created_at >= day_start, Chat.created_at < day_end).count()
        labels.append(day.strftime("%d %b"))
        counts.append(c)

    return jsonify({
        "today_visitors": today_visitors,
        "online_visitors": online_visitors,
        "offline_visitors": offline_visitors,
        "unread_chats": unread_chats,
        "total_chats": total_chats,
        "active_agents": active_agents,
        "avg_response_minutes": avg_response,
        "chart_labels": labels,
        "chart_counts": counts,
    })


# ---------------------------------------------------------------------------
# API: Inbox / Chats
# ---------------------------------------------------------------------------

@admin_bp.route("/api/chats")
@login_required
@permission_required("inbox.view")
def api_chats():
    status = request.args.get("status", "open")
    search = sanitize_text(request.args.get("search", ""), 100)

    query = Chat.query.join(Visitor)
    if status != "all":
        query = query.filter(Chat.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Visitor.name.ilike(like), Visitor.visitor_uid.ilike(like), Visitor.mobile.ilike(like))
        )
    chats = query.order_by(Chat.last_message_at.desc()).limit(100).all()

    result = []
    for c in chats:
        last_msg = c.messages[-1] if c.messages else None
        result.append({
            "chat_id": c.id,
            "visitor_id": c.visitor.id,
            "visitor_uid": c.visitor.visitor_uid,
            "visitor_name": c.visitor.name or c.visitor.visitor_uid,
            "is_online": c.visitor.is_online,
            "is_vip": c.visitor.is_vip,
            "status": c.status,
            "unread_count": c.unread_count,
            "assigned_admin": c.assigned_admin.name if c.assigned_admin else None,
            "last_message": (last_msg.content[:80] if last_msg else ""),
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        })
    return jsonify({"chats": result})


@admin_bp.route("/api/chats/<int:chat_id>")
@login_required
@permission_required("inbox.view")
def api_chat_detail(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    v = chat.visitor
    return jsonify({
        "chat_id": chat.id,
        "status": chat.status,
        "assigned_admin_id": chat.assigned_admin_id,
        "messages": [m.to_dict() for m in chat.messages],
        "visitor": {
            "id": v.id, "visitor_uid": v.visitor_uid, "name": v.name, "mobile": v.mobile,
            "email": v.email, "company": v.company, "browser": v.browser, "os": v.os,
            "device": v.device, "country": v.country, "city": v.city, "ip_address": v.ip_address,
            "current_page": v.current_page, "language": v.language, "is_online": v.is_online,
            "visit_count": v.visit_count, "tags": v.get_tags(), "is_vip": v.is_vip,
            "is_blocked": v.is_blocked, "lead_score": v.lead_score, "notes": v.notes,
        },
    })


@admin_bp.route("/api/chats/<int:chat_id>/assign", methods=["POST"])
@login_required
@permission_required("inbox.assign")
def api_assign_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    admin_id = request.json.get("admin_id") if request.is_json else None
    chat.assigned_admin_id = admin_id
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/chats/<int:chat_id>/close", methods=["POST"])
@login_required
@permission_required("inbox.close")
def api_close_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    chat.status = "closed"
    chat.closed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/chats/<int:chat_id>/archive", methods=["POST"])
@login_required
@permission_required("inbox.close")
def api_archive_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    chat.status = "archived"
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/chats/<int:chat_id>/block", methods=["POST"])
@login_required
@permission_required("visitors.manage")
def api_block_visitor(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    chat.visitor.is_blocked = True
    chat.is_blocked = True
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/chats/<int:chat_id>", methods=["DELETE"])
@login_required
@permission_required("inbox.delete")
def api_delete_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    db.session.delete(chat)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/chats/<int:chat_id>/export/csv")
@login_required
@permission_required("inbox.view")
def export_chat_csv(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Time", "Sender", "Message"])
    for m in chat.messages:
        writer.writerow([m.created_at.strftime("%Y-%m-%d %H:%M:%S"), m.sender_name or m.sender_type, m.content])
    buf.seek(0)
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=chat_{chat_id}.csv"},
    )


@admin_bp.route("/api/chats/<int:chat_id>/export/pdf")
@login_required
@permission_required("inbox.view")
def export_chat_pdf(chat_id):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    chat = Chat.query.get_or_404(chat_id)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"Chat Transcript - {chat.visitor.visitor_uid}", styles["Title"]), Spacer(1, 12)]
    for m in chat.messages:
        who = m.sender_name or m.sender_type
        line = f"<b>{who}</b> ({m.created_at.strftime('%Y-%m-%d %H:%M')}): {m.content}"
        story.append(Paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 6))
    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"chat_{chat_id}.pdf")


# ---------------------------------------------------------------------------
# API: Visitors
# ---------------------------------------------------------------------------

@admin_bp.route("/api/visitors")
@login_required
@permission_required("visitors.view")
def api_visitors():
    search = sanitize_text(request.args.get("search", ""), 100)
    filt = request.args.get("filter", "all")

    query = Visitor.query
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(Visitor.name.ilike(like), Visitor.visitor_uid.ilike(like), Visitor.mobile.ilike(like)))
    if filt == "vip":
        query = query.filter_by(is_vip=True)
    elif filt == "blocked":
        query = query.filter_by(is_blocked=True)
    elif filt == "returning":
        query = query.filter(Visitor.visit_count > 1)
    elif filt == "new":
        query = query.filter(Visitor.visit_count == 1)

    visitors = query.order_by(Visitor.last_seen.desc()).limit(200).all()
    return jsonify({"visitors": [{
        "id": v.id, "visitor_uid": v.visitor_uid, "name": v.name, "mobile": v.mobile,
        "email": v.email, "is_online": v.is_online, "is_vip": v.is_vip, "is_blocked": v.is_blocked,
        "visit_count": v.visit_count, "lead_score": v.lead_score, "tags": v.get_tags(),
        "last_seen": v.last_seen.isoformat() if v.last_seen else None,
        "country": v.country, "city": v.city,
    } for v in visitors]})


@admin_bp.route("/api/visitors/<int:visitor_id>", methods=["PATCH"])
@login_required
@permission_required("visitors.manage")
def api_update_visitor(visitor_id):
    v = Visitor.query.get_or_404(visitor_id)
    data = request.get_json(silent=True) or {}
    if "is_vip" in data:
        v.is_vip = bool(data["is_vip"])
    if "is_blocked" in data:
        v.is_blocked = bool(data["is_blocked"])
    if "lead_score" in data:
        v.lead_score = int(data["lead_score"])
    if "notes" in data:
        v.notes = sanitize_text(data["notes"], 4000)
    if "tags" in data and isinstance(data["tags"], list):
        v.set_tags(data["tags"])
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/visitors/export")
@login_required
@permission_required("visitors.manage")
def export_visitors_excel():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Visitors"
    ws.append(["Visitor ID", "Name", "Mobile", "Email", "Country", "City", "Visits", "Lead Score", "VIP", "Blocked"])
    for v in Visitor.query.all():
        ws.append([v.visitor_uid, v.name, v.mobile, v.email, v.country, v.city, v.visit_count, v.lead_score, v.is_vip, v.is_blocked])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name="visitors.xlsx",
    )


# ---------------------------------------------------------------------------
# API: FAQ
# ---------------------------------------------------------------------------

@admin_bp.route("/api/faq", methods=["POST"])
@login_required
@permission_required("faq.manage")
def api_create_faq():
    data = request.get_json(silent=True) or {}
    faq = FAQ(
        question=sanitize_text(data.get("question"), 255),
        answer=sanitize_text(data.get("answer"), 4000),
        category=sanitize_text(data.get("category") or "General", 80),
        sort_order=int(data.get("sort_order") or 0),
    )
    db.session.add(faq)
    db.session.commit()
    return jsonify({"success": True, "id": faq.id})


@admin_bp.route("/api/faq/<int:faq_id>", methods=["PUT", "DELETE"])
@login_required
@permission_required("faq.manage")
def api_faq_detail(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    if request.method == "DELETE":
        db.session.delete(faq)
        db.session.commit()
        return jsonify({"success": True})

    data = request.get_json(silent=True) or {}
    faq.question = sanitize_text(data.get("question"), 255) or faq.question
    faq.answer = sanitize_text(data.get("answer"), 4000) or faq.answer
    faq.category = sanitize_text(data.get("category"), 80) or faq.category
    faq.is_active = bool(data.get("is_active", faq.is_active))
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# API: Canned Replies
# ---------------------------------------------------------------------------

@admin_bp.route("/api/canned", methods=["GET"])
@login_required
@permission_required("inbox.view")
def api_list_canned():
    replies = CannedReply.query.all()
    return jsonify({"replies": [{"id": r.id, "shortcut": r.shortcut, "message": r.message} for r in replies]})


@admin_bp.route("/api/canned", methods=["POST"])
@login_required
@permission_required("canned.manage")
def api_create_canned():
    data = request.get_json(silent=True) or {}
    shortcut = sanitize_text(data.get("shortcut"), 50)
    if not shortcut.startswith("/"):
        shortcut = "/" + shortcut
    if not is_valid_shortcut(shortcut):
        return jsonify({"error": "Invalid shortcut. Use letters/numbers only, e.g. /price"}), 400
    if CannedReply.query.filter_by(shortcut=shortcut).first():
        return jsonify({"error": "Shortcut already exists"}), 400

    reply = CannedReply(shortcut=shortcut, message=sanitize_text(data.get("message"), 4000), created_by=current_user.id)
    db.session.add(reply)
    db.session.commit()
    return jsonify({"success": True, "id": reply.id})


@admin_bp.route("/api/canned/<int:reply_id>", methods=["PUT", "DELETE"])
@login_required
@permission_required("canned.manage")
def api_canned_detail(reply_id):
    reply = CannedReply.query.get_or_404(reply_id)
    if request.method == "DELETE":
        db.session.delete(reply)
        db.session.commit()
        return jsonify({"success": True})

    data = request.get_json(silent=True) or {}
    reply.message = sanitize_text(data.get("message"), 4000) or reply.message
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# API: Business Hours
# ---------------------------------------------------------------------------

@admin_bp.route("/api/business-hours", methods=["POST"])
@login_required
@permission_required("automation.manage")
def api_save_business_hours():
    data = request.get_json(silent=True) or {}
    days = data.get("days", [])
    for d in days:
        row = BusinessHours.query.filter_by(day_of_week=d["day_of_week"]).first()
        if not row:
            row = BusinessHours(day_of_week=d["day_of_week"])
            db.session.add(row)
        row.open_time = d.get("open_time", "09:00")
        row.close_time = d.get("close_time", "18:00")
        row.is_closed = bool(d.get("is_closed", False))
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# API: Admin / Role management (Owner only via admins.manage)
# ---------------------------------------------------------------------------

@admin_bp.route("/api/admins", methods=["GET"])
@login_required
@permission_required("inbox.view")
def api_list_admins():
    admins = Admin.query.filter_by(is_active_agent=True).all()
    return jsonify({"admins": [{"id": a.id, "name": a.name, "is_online": a.is_online} for a in admins]})


@admin_bp.route("/api/admins", methods=["POST"])
@login_required
@permission_required("admins.manage")
def api_create_admin():
    data = request.get_json(silent=True) or {}
    email = sanitize_text(data.get("email"), 120).lower()
    if Admin.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400

    role = Role.query.get(data.get("role_id"))
    if not role:
        return jsonify({"error": "Invalid role"}), 400

    admin = Admin(name=sanitize_text(data.get("name"), 120), email=email, role_id=role.id)
    admin.set_password(data.get("password") or "changeme123")
    db.session.add(admin)
    db.session.commit()
    return jsonify({"success": True, "id": admin.id})


@admin_bp.route("/api/admins/<int:admin_id>", methods=["PUT", "DELETE"])
@login_required
@permission_required("admins.manage")
def api_admin_detail(admin_id):
    target = Admin.query.get_or_404(admin_id)
    if request.method == "DELETE":
        if target.id == current_user.id:
            return jsonify({"error": "Cannot delete yourself"}), 400
        db.session.delete(target)
        db.session.commit()
        return jsonify({"success": True})

    data = request.get_json(silent=True) or {}
    if "role_id" in data:
        target.role_id = data["role_id"]
    if "is_active_agent" in data:
        target.is_active_agent = bool(data["is_active_agent"])
    if data.get("password"):
        target.set_password(data["password"])
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/roles")
@login_required
@permission_required("admins.manage")
def api_roles():
    roles = Role.query.all()
    return jsonify({"roles": [{"id": r.id, "name": r.name, "permissions": r.get_permissions()} for r in roles]})
