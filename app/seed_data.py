"""Shared logic to create default roles, an Owner admin, default settings,
and default business hours. Called both by seed.py (manual/build-time) and
automatically on every app startup (app/__init__.py) so the app self-heals
even if a hosting platform's build command didn't run seed.py."""

from app.extensions import db
from app.models import (
    Admin, BusinessHours, Role, Setting, DEFAULT_ROLE_PERMISSIONS,
    DEFAULT_SETTINGS,
)

DEFAULT_OWNER_EMAIL = "owner@example.com"
DEFAULT_OWNER_PASSWORD = "Owner@123"


def ensure_seed_data():
    """Idempotent: safe to call on every startup. Only creates what's missing."""
    db.create_all()

    role_map = {}
    for role_name, perms in DEFAULT_ROLE_PERMISSIONS.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            db.session.add(role)
        role.set_permissions(perms)
        role_map[role_name] = role
    db.session.flush()

    if not Admin.query.filter_by(email=DEFAULT_OWNER_EMAIL).first():
        owner = Admin(name="Owner", email=DEFAULT_OWNER_EMAIL, role_id=role_map["Owner"].id)
        owner.set_password(DEFAULT_OWNER_PASSWORD)
        db.session.add(owner)

    for key, value in DEFAULT_SETTINGS.items():
        if not Setting.query.get(key):
            db.session.add(Setting(key=key, value=value))

    if BusinessHours.query.count() == 0:
        for day in range(7):
            db.session.add(BusinessHours(
                day_of_week=day, open_time="09:00", close_time="18:00",
                is_closed=(day >= 5),
            ))

    db.session.commit()
