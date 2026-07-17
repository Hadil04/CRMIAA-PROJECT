"""
Application configuration.

All sensitive / environment-specific values are loaded from the `.env` file so
that they never live in source control. See `.env.example` for the full list of
supported variables.

To add a new configuration value:
    1. Add it to `.env` (and document it in `.env.example`).
    2. Read it here with `os.getenv(...)` and expose it as a class attribute.
    3. Access it anywhere via `current_app.config["YOUR_KEY"]`.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

# Load variables from the local .env file into the process environment.
load_dotenv()


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    """Base configuration shared by all environments."""

    # Secret used to sign the session cookie. MUST be set to a long random value
    # in production (see README). Accepts SECRET_KEY or the older FLASK_SECRET_KEY.
    SECRET_KEY = (
        os.getenv("SECRET_KEY")
        or os.getenv("FLASK_SECRET_KEY")
        or "dev-only-insecure-key"
    )

    # ---- SQL Server connection (values below are read from .env) -----------
    DB_SERVER = os.getenv("DB_SERVER", ".")
    DB_NAME = os.getenv("DB_NAME", "CRMIAA")
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")

    # Auth mode: Windows Authentication by default (Trusted_Connection=yes).
    # For SQL Server logins, set DB_TRUSTED_CONNECTION=no and provide DB_USERNAME/DB_PASSWORD.
    DB_TRUSTED_CONNECTION = _as_bool(os.getenv("DB_TRUSTED_CONNECTION", "yes"))
    DB_USERNAME = os.getenv("DB_USERNAME", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # Transport security (Driver 18 defaults to Encrypt=yes; keep TrustServerCertificate
    # =yes for local/self-signed instances).
    DB_ENCRYPT = os.getenv("DB_ENCRYPT", "yes")
    DB_TRUST_SERVER_CERTIFICATE = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")
    DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", "5"))

    # Limit uploads, including Excel imports, to 5 MB.
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # ---- Session hardening -------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set to True once the app is served over HTTPS.
    SESSION_COOKIE_SECURE = _as_bool(os.getenv("SESSION_COOKIE_SECURE", "false"))
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


# Map a name -> config class so the app factory can pick one by env var later.
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
