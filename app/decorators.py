from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user


def permission_required(permission):
    """Restrict a route to admins whose role includes `permission`."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_permission(permission):
                if request.path.startswith("/admin/api/"):
                    return jsonify({"error": "Permission denied"}), 403
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator
