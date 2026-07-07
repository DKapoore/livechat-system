from flask import Blueprint

widget_bp = Blueprint("widget", __name__, url_prefix="/widget")

from app.widget import routes  # noqa: E402,F401
