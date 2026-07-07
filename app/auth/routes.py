from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, login_required, current_user

from app.auth import auth_bp
from app.extensions import db
from app.models import Admin, Log
from app.utils import sanitize_text


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = sanitize_text(request.form.get("email"), 120).lower()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(email=email).first()
        if admin and admin.check_password(password) and admin.is_active_agent:
            login_user(admin, remember=False)
            admin.last_login = datetime.utcnow()
            admin.is_online = True
            db.session.add(Log(admin_id=admin.id, action="login", details=f"{email} logged in"))
            db.session.commit()
            return redirect(url_for("admin.dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("admin/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    current_user.is_online = False
    db.session.add(Log(admin_id=current_user.id, action="logout", details=f"{current_user.email} logged out"))
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))
