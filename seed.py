"""Run once (optional) to initialize the database manually:

    python seed.py

Note: the app now also runs this automatically on every startup
(see app/__init__.py -> ensure_seed_data()), so this script is mainly
useful for local testing or forcing a re-check without starting the server.
"""
from app import create_app
from app.seed_data import ensure_seed_data, DEFAULT_OWNER_EMAIL, DEFAULT_OWNER_PASSWORD

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        ensure_seed_data()
        print("Database initialized.")
        print(f"Owner login -> email: {DEFAULT_OWNER_EMAIL}  password: {DEFAULT_OWNER_PASSWORD}")
        print("IMPORTANT: change this password immediately after first login.")
