"""User data access + authentication + user creation.

This project authenticates using a SQL Server `Users` table.

Schema expected:
    Id            INT IDENTITY PRIMARY KEY
    Username      NVARCHAR(100) UNIQUE NOT NULL
    PasswordHash  NVARCHAR(255)  NOT NULL
    Role          NVARCHAR(50)   NOT NULL
    IsActive      BIT            NOT NULL
    CreatedAt     DATETIME2      NOT NULL

Passwords are stored hashed (Werkzeug). For safety, login uses
`verify_password()` and blocks disabled accounts (IsActive=0).
"""

import hmac

from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_connection


# Prefixes produced by Werkzeug password hashing.
_HASH_PREFIXES = ("pbkdf2:", "scrypt:", "argon2")


def get_user_by_username(username: str):
    """Return a user dict for the given username, or None if not found."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT Id, Username, PasswordHash, Role, IsActive "
            "FROM Users WHERE Username = ?",
            username,
        )
        row = cur.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "username": row[1],
        "password_hash": row[2],
        "role": row[3],
        "is_active": bool(row[4]),
    }


def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Check a submitted password against the stored value."""
    if not stored_hash:
        return False

    # Properly hashed password -> use Werkzeug's constant-time verifier.
    if stored_hash.startswith(_HASH_PREFIXES):
        try:
            return check_password_hash(stored_hash, provided_password)
        except Exception:
            return False

    # Legacy plaintext fallback (constant-time). Re-hash ASAP.
    return hmac.compare_digest(
        stored_hash.encode("utf-8"), provided_password.encode("utf-8")
    )


def authenticate(username: str, password: str):
    """Return the user dict if credentials are valid AND the account is active."""
    user = get_user_by_username(username)
    if user is None or not user["is_active"]:
        return None

    if verify_password(user["password_hash"], password):
        return user
    return None


def create_user(username: str, password: str, role: str = "User"):
    """Create a new user account with a hashed password.

    - If username already exists, returns None (caller decides the message).
    - Always sets IsActive=1 for new accounts.
    """
    password_hash = generate_password_hash(password)

    with get_connection() as conn:
        cur = conn.cursor()

        # Check existence first to provide a clean, user-friendly behavior.
        cur.execute("SELECT Id FROM Users WHERE Username = ?", username)
        exists = cur.fetchone() is not None
        if exists:
            return None

        cur.execute(
            "INSERT INTO Users (Username, PasswordHash, Role, IsActive) "
            "VALUES (?, ?, ?, 1)",
            username,
            password_hash,
            role,
        )
        conn.commit()

    return True

