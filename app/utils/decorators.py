"""
Reusable view decorators.

`login_required` protects any route that should only be reachable by an
authenticated admin. Apply it to future protected pages like so:

    from app.utils.decorators import login_required

    @some_bp.route("/secret")
    @login_required
    def secret():
        ...
"""
from functools import wraps

from flask import flash, redirect, request, session, url_for


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        """Protect a route so only authenticated users can access it."""
        if not session.get("logged_in"):
            flash("Please log in to access that page.", "warning")
            # Remember where the user was headed so we can send them back.
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def role_required(expected_role: str):
    """Protect a route so only users with a specific role can access it.

    This project uses session-based authentication (not Flask-Login).
    We rely on `session['role']` which is set during login.

    Usage:
        @login_required
        @role_required('Admin')
        def some_admin_route():
            ...
    """

    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            actual_role = session.get("role")
            if actual_role != expected_role:
                flash("You do not have permission to access that page.", "warning")
                # Redirect to the correct dashboard based on their role.
                if actual_role == "Admin":
                    return redirect(url_for("admin.dashboard"))
                return redirect(url_for("user.dashboard"))

            return view(*args, **kwargs)

        return wrapped_view

    return decorator

