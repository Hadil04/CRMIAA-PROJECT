"""User routes.

User pages are protected by:
  - `@login_required` to ensure the user is authenticated
  - `@role_required('User')` to ensure the user is not an Admin

This keeps routing and authorization consistent across the project.
"""

from flask import render_template, session

from app.user import user_bp
from app.utils.decorators import login_required, role_required


@user_bp.route("/dashboard")
@login_required
@role_required("User")
def dashboard():
    """User dashboard."""
    return render_template(
        "user/dashboard.html",
        username=session.get("username", "User"),
    )

