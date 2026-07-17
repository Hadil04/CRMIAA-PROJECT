"""User blueprint: dedicated user dashboard."""

from flask import Blueprint

user_bp = Blueprint("user", __name__, url_prefix="/user")

from app.user import routes  # noqa: E402,F401 (import after bp is defined)

