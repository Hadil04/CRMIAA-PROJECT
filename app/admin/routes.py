"""
Admin routes.

Every view here is protected by `@login_required`. Add new admin pages by
declaring more routes in this file (or by creating additional blueprints for
larger feature areas and registering them in `app/__init__.py`).
"""
import pyodbc
import secrets
from zipfile import BadZipFile
from datetime import date
from io import BytesIO

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from werkzeug.security import generate_password_hash

from app.admin import admin_bp
from app.auth.repository import authenticate
from app.db import get_connection
from app.utils.decorators import login_required, role_required


ALLOWED_EXCEL_MIMETYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
ALLOWED_IMPORT_ROLES = {"Admin", "User"}


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin sign-in page."""
    if session.get("logged_in"):
        if session.get("role") == "Admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("user.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            user = authenticate(username, password)
        except pyodbc.Error as exc:
            current_app.logger.error("Database error during admin login: %s", exc)
            flash(
                "Could not reach the database. Please contact the administrator.",
                "error",
            )
            return render_template("admin/login.html"), 503

        if user and user["role"] == "Admin":
            session.clear()
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session.permanent = True
            return redirect(url_for("admin.dashboard"))

        flash("Admin access is required.", "error")
        return render_template("admin/login.html"), 401

    return render_template("admin/login.html")


@admin_bp.route("/" )
@admin_bp.route("/dashboard")
@login_required
@role_required("Admin")
def dashboard():
    return render_template(
        "admin/dashboard.html",
        username=session.get("username", "Admin"),
    )


@admin_bp.route("/reports")
@login_required
@role_required("Admin")
def reports():
    """Reports page with Excel import tools (Admin only)."""
    return render_template(
        "admin/reports.html",
        username=session.get("username", "Admin"),
    )


def _clean_cell(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_header(value):
    return _clean_cell(value).lower()


def _normalize_role(value):
    role = _clean_cell(value).title()
    if role not in ALLOWED_IMPORT_ROLES:
        return ""
    return role


def _row_value(row, header_map, column_name):
    index = header_map.get(column_name)
    if index is None or index >= len(row):
        return ""
    return row[index]


def _placeholder_password_hash():
    return generate_password_hash(secrets.token_urlsafe(32))


@admin_bp.route("/reports/import", methods=["POST"])
@login_required
@role_required("Admin")
def import_report_users():
    """Import users from an uploaded Excel workbook (Admin only)."""
    upload = request.files.get("excel_file")
    if not upload or not upload.filename:
        flash("Please choose an Excel file to import.", "warning")
        return redirect(url_for("admin.reports"))

    filename = upload.filename.strip().lower()
    if not filename.endswith(".xlsx"):
        flash("Only .xlsx Excel files are supported.", "warning")
        return redirect(url_for("admin.reports"))

    if upload.mimetype not in ALLOWED_EXCEL_MIMETYPES:
        flash("The uploaded file does not look like a valid .xlsx file.", "warning")
        return redirect(url_for("admin.reports"))

    try:
        workbook = load_workbook(upload.stream, read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, OSError, ValueError):
        flash("The uploaded file could not be opened as a valid Excel workbook.", "error")
        return redirect(url_for("admin.reports"))

    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)
    headers = next(rows, None)
    if not headers:
        flash("The Excel file is empty.", "warning")
        return redirect(url_for("admin.reports"))

    header_map = {
        _normalize_header(header): index
        for index, header in enumerate(headers)
        if _normalize_header(header)
    }
    required_columns = {"username", "role"}
    missing_columns = sorted(required_columns - set(header_map))
    if missing_columns:
        flash(
            "Missing required column(s): " + ", ".join(missing_columns),
            "warning",
        )
        return redirect(url_for("admin.reports"))

    imported_count = 0
    skipped = []
    seen_usernames = set()

    with get_connection() as conn:
        cur = conn.cursor()

        for excel_row_number, row in enumerate(rows, start=2):
            username = _clean_cell(_row_value(row, header_map, "username"))
            role = _normalize_role(_row_value(row, header_map, "role"))
            password = _clean_cell(_row_value(row, header_map, "password"))

            if not username:
                skipped.append(f"row {excel_row_number} missing Username")
                continue
            if len(username) > 100:
                skipped.append(f"row {excel_row_number} Username is too long")
                continue
            if not role:
                skipped.append(f"row {excel_row_number} has invalid Role")
                continue
            if password and len(password) < 6:
                skipped.append(f"row {excel_row_number} password is too short")
                continue

            username_key = username.lower()
            if username_key in seen_usernames:
                skipped.append(f"row {excel_row_number} duplicate Username")
                continue
            seen_usernames.add(username_key)

            cur.execute("SELECT Id FROM Users WHERE Username = ?", username)
            existing = cur.fetchone()

            if existing:
                if password:
                    cur.execute(
                        "UPDATE Users SET PasswordHash = ?, Role = ?, IsActive = 1 "
                        "WHERE Username = ?",
                        generate_password_hash(password), role, username,
                    )
                else:
                    cur.execute(
                        "UPDATE Users SET Role = ? WHERE Username = ?",
                        role, username,
                    )
            else:
                if password:
                    password_hash = generate_password_hash(password)
                    is_active = 1
                else:
                    password_hash = _placeholder_password_hash()
                    is_active = 0

                cur.execute(
                    "INSERT INTO Users (Username, PasswordHash, Role, IsActive) "
                    "VALUES (?, ?, ?, ?)",
                    username, password_hash, role, is_active,
                )

            imported_count += 1

        conn.commit()

    if skipped:
        preview = "; ".join(skipped[:5])
        if len(skipped) > 5:
            preview += f"; and {len(skipped) - 5} more"
        flash(
            f"{imported_count} rows imported, {len(skipped)} skipped: {preview}.",
            "warning",
        )
    else:
        flash(f"{imported_count} rows imported successfully.", "success")

    return redirect(url_for("admin.reports"))


@admin_bp.route("/users")
@login_required
@role_required("Admin")
def users_page():
    """List all users (Admin only)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT Id, Username, Role, IsActive FROM Users ORDER BY Id"
        )
        rows = cur.fetchall()

    users = [
        {
            "id": r[0],
            "username": r[1],
            "role": r[2],
            "is_active": bool(r[3]),
        }
        for r in rows
    ]

    return render_template(
        "admin/users.html",
        username=session.get("username", "Admin"),
        users=users,
    )


@admin_bp.route("/users/export")
@login_required
@role_required("Admin")
def export_users():
    """Export users to an Excel workbook (Admin only)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT Id, Username, Role, IsActive, CreatedAt FROM Users ORDER BY Id"
        )
        rows = cur.fetchall()

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Users"
    worksheet.append(["Id", "Username", "Role", "IsActive", "CreatedAt"])

    for row in rows:
        worksheet.append(
            [
                row[0],
                row[1],
                row[2],
                "Yes" if row[3] else "No",
                row[4],
            ]
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = f"users_export_{date.today().isoformat()}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _count_active_admins(exclude_user_id=None):
    with get_connection() as conn:
        cur = conn.cursor()
        if exclude_user_id is None:
            cur.execute(
                "SELECT COUNT(1) FROM Users WHERE Role = 'Admin' AND IsActive = 1"
            )
            return int(cur.fetchone()[0])
        cur.execute(
            "SELECT COUNT(1) FROM Users WHERE Role = 'Admin' AND IsActive = 1 AND Id <> ?",
            exclude_user_id,
        )
        return int(cur.fetchone()[0])


@admin_bp.route("/users/<int:user_id>/toggle-role", methods=["POST"])
@login_required
@role_required("Admin")
def toggle_user_role(user_id: int):
    """Promote to Admin or demote to User (Admin only).

    Safety: prevent demoting the last active admin.
    """
    action = request.form.get("action", "").strip().lower()
    if action not in {"promote", "demote"}:
        flash("Invalid role action.", "error")
        return redirect(f"{admin_bp.url_prefix}/users")

    with get_connection() as conn:
        cur = conn.cursor()

        # If demoting/promoting, we update Role and ensure IsActive stays 1.
        if action == "demote":
            # Safety: if this user is the last active admin, block.
            # Exclude current user id from count.
            remaining = _count_active_admins(exclude_user_id=user_id)
            if remaining <= 0:
                flash("Cannot demote: you must keep at least one active administrator.", "warning")
                return redirect(f"{admin_bp.url_prefix}/users")
            cur.execute(
                "UPDATE Users SET Role = 'User' WHERE Id = ?",
                user_id,
            )
        else:
            cur.execute(
                "UPDATE Users SET Role = 'Admin' WHERE Id = ?",
                user_id,
            )

        conn.commit()

    flash("User role updated.", "success")
    return redirect(f"{admin_bp.url_prefix}/users")


@admin_bp.route("/users/<int:user_id>/disable", methods=["POST"])
@login_required
@role_required("Admin")
def disable_user(user_id: int):
    """Disable (IsActive=0) a user (Admin only).

    Safety: prevent disabling the last active admin.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT Role FROM Users WHERE Id = ?",
            user_id,
        )
        row = cur.fetchone()
        if not row:
            flash("User not found.", "error")
            return redirect(f"{admin_bp.url_prefix}/users")

        role = row[0]

        if role == "Admin":
            remaining = _count_active_admins(exclude_user_id=user_id)
            if remaining <= 0:
                flash("Cannot disable: you must keep at least one active administrator.", "warning")
                return redirect(f"{admin_bp.url_prefix}/users")

        cur.execute(
            "UPDATE Users SET IsActive = 0 WHERE Id = ?",
            user_id,
        )
        conn.commit()

    flash("User disabled.", "success")
    return redirect(f"{admin_bp.url_prefix}/users")
