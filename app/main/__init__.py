"""Main blueprint: entry point / root routing."""
from flask import Blueprint

main_bp = Blueprint("main", __name__)

from app.main import routes  # noqa: E402,F401  (import after bp is defined)
