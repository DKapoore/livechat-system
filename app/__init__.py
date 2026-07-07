import os

from flask import Flask, send_from_directory

from config import Config
from app.extensions import db, login_manager, socketio


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(app.instance_path), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, async_mode=app.config.get("SOCKETIO_ASYNC_MODE", "threading"))

    from app.models import Admin

    @login_manager.user_loader
    def load_user(user_id):
        return Admin.query.get(int(user_id))

    # Blueprints
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.widget import widget_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(widget_bp)

    # Socket event handlers register themselves on import
    from app import sockets  # noqa: F401

    # Convenience route so the embed snippet can use /widget.js directly
    @app.route("/widget.js")
    def widget_js():
        return send_from_directory(
            os.path.join(app.root_path, "static", "widget"), "widget.js",
            mimetype="application/javascript",
        )

    @app.route("/")
    def index():
        return (
            "<h2>Live Chat System is running.</h2>"
            "<p>Admin panel: <a href='/admin/login'>/admin/login</a></p>"
            "<p>Demo page with widget: <a href='/demo'>/demo</a></p>"
        )

    @app.route("/demo")
    def demo():
        api_key = Config.DEFAULT_API_KEY
        return f"""
        <html>
        <head><title>Demo Website</title></head>
        <body style="font-family:sans-serif;padding:60px;">
            <h1>Welcome to the Demo Website</h1>
            <p>This page embeds the floating live chat widget in the bottom-right corner.</p>
            <script src="/widget.js"></script>
            <script>
                LiveChat.init({{ apiKey: "{api_key}" }});
            </script>
        </body>
        </html>
        """

    return app
