"""Run once to initialize the database:

    python seed.py

Creates tables, default roles + permissions, a default Owner admin login,
default settings, and Mon-Fri 09:00-18:00 business hours.
"""
from app import create_app
from app.extensions import db
from app.models import (
    Admin, BusinessHours, Role, Setting, DEFAULT_ROLE_PERMISSIONS,
    DEFAULT_SETTINGS,
)

app = create_app()

DEFAULT_OWNER_EMAIL = "owner@example.com"
DEFAULT_OWNER_PASSWORD = "Owner@123"


def run():
    with app.app_context():
        db.create_all()

        # Roles
        role_map = {}
        for role_name, perms in DEFAULT_ROLE_PERMISSIONS.items():
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name)
                db.session.add(role)
            role.set_permissions(perms)
            role_map[role_name] = role
        db.session.flush()

        # Default owner admin
        if not Admin.query.filter_by(email=DEFAULT_OWNER_EMAIL).first():
            owner = Admin(name="Owner", email=DEFAULT_OWNER_EMAIL, role_id=role_map["Owner"].id)
            owner.set_password(DEFAULT_OWNER_PASSWORD)
            db.session.add(owner)

        # Default settings
        for key, value in DEFAULT_SETTINGS.items():
            if not Setting.query.get(key):
                db.session.add(Setting(key=key, value=value))

        # Default business hours: Mon-Fri 09:00-18:00, Sat-Sun closed
        if BusinessHours.query.count() == 0:
            for day in range(7):
                db.session.add(BusinessHours(
                    day_of_week=day,
                    open_time="09:00",
                    close_time="18:00",
                    is_closed=(day >= 5),
                ))

        db.session.commit()
        print("Database initialized.")
        print(f"Owner login -> email: {DEFAULT_OWNER_EMAIL}  password: {DEFAULT_OWNER_PASSWORD}")
        print("IMPORTANT: change this password immediately after first login.")


if __name__ == "__main__":
    run()
