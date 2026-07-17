"""
Authentication routes.

Credentials are validated against the `Users` table in SQL Server (see
`app/auth/repository.py`). Connection settings come from `.env` via `config.py`.
"""
import pyodbc
from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.auth import auth_bp
from app.auth.repository import authenticate, create_user



@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in? Skip the form.
    if session.get("logged_in"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            user = authenticate(username, password)
        except pyodbc.Error as exc:
            # Database unreachable / misconfigured — don't leak details to the user.
            current_app.logger.error("Database error during login: %s", exc)
            flash(
                "Could not reach the database. Please contact the administrator.",
                "error",
            )
            return render_template("auth/login.html"), 503

        if user:
            session.clear()
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session.permanent = True

            # After successful login, redirect based on role.
            # Requirement: Admin -> /admin/dashboard, User -> /user/dashboard
            role = session.get("role")
            if role == "Admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("user.dashboard"))


        flash("Invalid username or password.", "error")
        return render_template("auth/login.html"), 401

    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Create a new USER account (role is always 'User').

    Public endpoint:
      - accessible from outside (no login required)
      - creates Users table row with hashed password
      - redirects to the correct dashboard based on role
    """
    # If already logged in, skip.
    if session.get("logged_in"):
        # Keep existing behavior: send based on role.
        role = session.get("role")
        if role == "Admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("user.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "warning")
            return render_template("auth/signup.html"), 400

        # Basic password length check (minimal, beginner-friendly).
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "warning")
            return render_template("auth/signup.html"), 400

        try:
            created = create_user(username=username, password=password, role="User")
        except pyodbc.Error as exc:
            current_app.logger.error("Database error during signup: %s", exc)
            flash(
                "Could not reach the database. Please contact the administrator.",
                "error",
            )
            return render_template("auth/signup.html"), 503

        if not created:
            flash("Username already exists. Please choose another.", "warning")
            return render_template("auth/signup.html"), 409

        flash("Account created. Please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/signup.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))

