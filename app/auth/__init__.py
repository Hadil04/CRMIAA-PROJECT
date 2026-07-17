"""Authentication blueprint: login / logout."""
from flask import Blueprint

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

from app.auth import routes  # noqa: E402,F401  (import after bp is defined)
