"""
Runtime database-settings persistence.

Why a JSON file and not .env?
------------------------------
`config.py` calls `load_dotenv()` once at import time, so writing to `.env`
at runtime has no effect on the running process.  We instead maintain a small
`db_settings.json` next to the project root that is:

  * loaded at app startup in `create_app()` and merged into `app.config`
  * re-merged into `app.config` every time the admin saves the Settings form
  * never committed to version control (.gitignore should include db_settings.json)

Only the DB connection fields are stored here — everything else stays in .env.
The password is stored as-is (the file lives on the server, not in the repo).
"""

import json
from pathlib import Path
from typing import Any

# Written next to manage.py / wsgi.py, not inside the package folder.
_SETTINGS_PATH = Path(__file__).parent.parent / "db_settings.json"

# Keys we manage — must match the names used in config.py / app/db.py.
DB_KEYS = (
    "DB_SERVER",
    "DB_NAME",
    "DB_USERNAME",
    "DB_PASSWORD",
    "DB_TRUSTED_CONNECTION",
    "DB_DRIVER",
    "DB_ENCRYPT",
    "DB_TRUST_SERVER_CERTIFICATE",
    "DB_TIMEOUT",
)


def load_db_settings() -> dict[str, Any]:
    """Return persisted DB settings, or an empty dict if none saved yet."""
    if not _SETTINGS_PATH.exists():
        return {}
    try:
        with _SETTINGS_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if k in DB_KEYS}
    except (json.JSONDecodeError, OSError):
        return {}


def save_db_settings(values: dict[str, Any]) -> None:
    """Persist a dict of DB settings, merging with any existing values.

    Only keys in DB_KEYS are written; unrecognised keys are silently dropped.
    """
    existing = load_db_settings()
    merged = {**existing, **{k: v for k, v in values.items() if k in DB_KEYS}}
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _SETTINGS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)


def apply_db_settings(app) -> None:
    """Merge persisted DB settings into a Flask app's config dict.

    Call this once in ``create_app()`` and again after every save so that
    ``current_app.config`` always reflects the latest settings.
    """
    settings = load_db_settings()
    if settings:
        app.config.update(settings)


def settings_have_password() -> bool:
    """Return True if a non-empty password is stored in db_settings.json."""
    data = load_db_settings()
    return bool(data.get("DB_PASSWORD", ""))
