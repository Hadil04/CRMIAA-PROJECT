"""
SQL Server database access.

Builds the ODBC connection string from configuration (loaded from `.env`) and
hands out `pyodbc` connections. Every value is configurable so the same code
runs unchanged on another machine — only that machine's `.env` differs.

Usage:
    from app.db import get_connection
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT ...")
"""
import pyodbc
from flask import current_app


def build_connection_string(cfg=None) -> str:
    """Assemble the ODBC connection string from Flask config."""
    cfg = cfg or current_app.config

    parts = [
        f"DRIVER={{{cfg['DB_DRIVER']}}}",
        f"SERVER={cfg['DB_SERVER']}",
        f"DATABASE={cfg['DB_NAME']}",
    ]

    if cfg["DB_TRUSTED_CONNECTION"]:
        # Windows Authentication — the OS user running the app is used.
        parts.append("Trusted_Connection=yes")
    else:
        # SQL Server authentication.
        parts.append(f"UID={cfg['DB_USERNAME']}")
        parts.append(f"PWD={cfg['DB_PASSWORD']}")

    parts.append(f"Encrypt={cfg['DB_ENCRYPT']}")
    parts.append(f"TrustServerCertificate={cfg['DB_TRUST_SERVER_CERTIFICATE']}")

    return ";".join(parts) + ";"


def get_connection(cfg=None):
    """Open a new pyodbc connection. Caller is responsible for closing it
    (use a `with` block, which closes automatically)."""
    cfg = cfg or current_app.config
    return pyodbc.connect(build_connection_string(cfg), timeout=cfg["DB_TIMEOUT"])
