"""Root routing: send visitors to the right place based on auth state."""
from flask import redirect, session, url_for

from app.main import main_bp


@main_bp.route("/")
def index():
    """Root routing based on auth state + role.

    After login:
      - Admin -> /admin/dashboard
      - User  -> /user/dashboard
    """
    if session.get("logged_in"):
        role = session.get("role")
        if role == "Admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("user.dashboard"))
    return redirect(url_for("auth.login"))

