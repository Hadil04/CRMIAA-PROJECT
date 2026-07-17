# CRMIAA

A Flask web application with a professional admin login backed by a **SQL Server**
`Users` table. Built with the **app-factory + blueprints** pattern so new
features can be added cleanly by any developer on the team.

---

## Features

- 🔐 Login validated against the SQL Server `Users` table (hashed passwords).
- 🎨 Professional, responsive login page + admin dashboard.
- 🧩 Modular structure (blueprints) — add new modules without touching auth.
- ⚙️ All connection settings & secrets in `.env` (nothing hard-coded).
- 🛠️ `manage.py` CLI to test the DB, create the table, and seed the admin.
- 🚫 Friendly 404 / 500 pages and a clear message if the DB is unreachable.

---

## Requirements

- **Python 3.10+**
- **SQL Server** with a `CRMIAA` database (any edition; default instance or a
  named instance such as `SQLEXPRESS`).
- A **Microsoft ODBC Driver for SQL Server** installed. Check which one you have:
  ```bash
  python -c "import pyodbc; print(pyodbc.drivers())"
  ```
  Put the exact name into `.env` → `DB_DRIVER` (e.g. `ODBC Driver 18 for SQL Server`
  or `ODBC Driver 17 for SQL Server`).

---

## Setup (on the machine that has the database)

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the connection
copy .env.example .env           # Windows  (cp on macOS/Linux)
#   Edit .env: set SECRET_KEY, DB_SERVER, DB_NAME, DB_DRIVER, and the auth mode.

# 4. Create the Users table (skip if it already exists)
python manage.py init-db
#   ...or run database/schema.sql in SSMS to create the DB + table.

# 5. Create the admin account (password is stored HASHED)
python manage.py create-admin hadil hadil123 Admin

# 6. Verify the connection any time
python manage.py test-db

# 7. Run the app
python run.py
```

Open <http://127.0.0.1:5000> and sign in.

**Admin login:** `hadil` / `hadil123` → you'll land on the **Welcome to CRMIAA**
dashboard.

## Local URLs

Use these URLs while the Flask dev server is running with `python run.py`:

| Page | URL |
| ---- | --- |
| Home / automatic redirect | <http://127.0.0.1:5000> |
| User sign-in | <http://127.0.0.1:5000/auth/login> |
| User sign-up | <http://127.0.0.1:5000/auth/signup> |
| Admin sign-in | <http://127.0.0.1:5000/admin/login> |
| Admin dashboard | <http://127.0.0.1:5000/admin/dashboard> |
| Reports / Excel import | <http://127.0.0.1:5000/admin/reports> |
| Manage users | <http://127.0.0.1:5000/admin/users> |
| Export users to Excel | <http://127.0.0.1:5000/admin/users/export> |

If the browser says `127.0.0.1 n'autorise pas la connexion`, start the server
first:

```bash
python run.py
```

> ℹ️ The password is never stored in plaintext. `create-admin` hashes it, and the
> login verifies the hash. If a row already contains a plaintext password, login
> still works (fallback) — but re-run `create-admin` to upgrade it to a hash.

---

## `manage.py` commands

| Command | What it does |
| ------- | ------------ |
| `python manage.py test-db` | Check the DB connection; show server / database / login. |
| `python manage.py init-db` | Create the `Users` table if it doesn't exist. |
| `python manage.py create-admin [user] [pass] [role]` | Create **or** update an admin (hashed). Defaults: `hadil hadil123 Admin`. |
| `python manage.py list-users` | List the accounts in the `Users` table. |

---

## `Users` table

| Column         | Type            | Notes                              |
| -------------- | --------------- | ---------------------------------- |
| `Id`           | INT IDENTITY PK |                                    |
| `Username`     | NVARCHAR(100)   | Unique                             |
| `PasswordHash` | NVARCHAR(255)   | werkzeug pbkdf2/scrypt hash        |
| `Role`         | NVARCHAR(50)    | e.g. `Admin`                       |
| `IsActive`     | BIT             | `0` blocks login                   |
| `CreatedAt`    | DATETIME2       | Defaults to `SYSUTCDATETIME()`     |

DDL lives in [database/schema.sql](database/schema.sql).

---

## Project structure

```text
CRMIAA/
├── run.py                  # Entry point — creates & runs the app
├── manage.py               # CLI: test-db / init-db / create-admin / list-users
├── config.py               # Configuration (reads .env)
├── requirements.txt        # Python dependencies
├── .env                    # Secrets & DB settings (NOT committed)
├── .env.example            # Template for .env
├── database/
│   └── schema.sql          # CREATE DATABASE + Users table
└── app/
    ├── __init__.py         # App factory + blueprint / error registration
    ├── db.py               # SQL Server connection (builds ODBC string)
    ├── main/               # Root routing (/)
    ├── auth/               # Login / logout
    │   ├── routes.py
    │   └── repository.py   # Users queries + password verification
    ├── admin/              # Protected dashboard & admin features
    ├── utils/decorators.py # @login_required
    ├── templates/          # Jinja2 HTML templates
    └── static/             # CSS & JS assets
```

---

## How to extend (for developers)

### Add a protected admin page
```python
from app.utils.decorators import login_required

@admin_bp.route("/reports")
@login_required
def reports():
    return render_template("admin/reports.html")
```

### Add a whole new feature area (module)
1. Create `app/<feature>/` with `__init__.py` (defining a `Blueprint`) and `routes.py`.
2. Register it in `app/__init__.py` → `register_blueprints()`.

### Query the database from your code
```python
from app.db import get_connection

with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT ... FROM ... WHERE Col = ?", value)
    rows = cur.fetchall()
```

### Add roles / authorization
`session["role"]` is set during login. Add a `role_required("Admin")` decorator in
`app/utils/decorators.py` following the same pattern as `login_required`.

---

## RBAC + default patterns (recommended)

This app uses **session-based auth** (not Flask-Login).

- Any authenticated page: decorate with `@login_required`.
- Any admin-only page: decorate with `@login_required` + `@role_required("Admin")`.
- Any user-only page: decorate with `@login_required` + `@role_required("User")`.

New feature routes should follow the same pattern by default.

---

## CRIA backend module

`app/cria/` contains isolated backend pieces for CRIA, the future AI agent
module. No routes, blueprints, or UI are wired up yet.

Files added:

| File | Purpose |
| ---- | ------- |
| `app/cria/data_loader.py` | `load_csv(path)` reads a CSV into a pandas `DataFrame` and raises clear errors for missing, empty, or malformed CSV files. |
| `app/cria/security.py` | `SensitiveDataMasker` masks hardcoded sensitive words with stable fake four-letter codes and can unmask them later. |
| `app/cria/ai_client.py` | `ask_ai(question)` masks the question, sends only the masked text to Gemini, unmasks the answer, and returns it. |
| `app/cria/test_data_loader.py` | Manual smoke test that loads `sample_data.csv`, then prints `.head()` and `.info()`. |
| `app/cria/test_security.py` | Manual smoke test that masks a sample sentence, prints it, then unmasks it. |
| `app/cria/test_ai_client.py` | Manual smoke test that prints the masked question sent to AI and the final unmasked answer. |
| `app/cria/sample_data.csv` | Small CSV file for manual loader testing. |

The masker currently detects these starter sensitive words:

```text
Ahmed, Sarah, school, salary
```

The real-word to fake-code mapping is saved locally at:

```text
app/cria/mask_map.json
```

That file is ignored by git because it may contain sensitive words.

### Configure CRIA AI

CRIA reads the Gemini API key from `.env`:

```text
GEMINI_API_KEY=your-real-gemini-api-key-here
```

Keep the real key only in `.env`. `.env.example` contains an empty placeholder.

### Test CRIA manually

Install or refresh dependencies first, because CRIA uses pandas:

```bash
pip install -r requirements.txt
```

Run the CSV loader smoke test from the project root:

```bash
python -m app.cria.test_data_loader
```

Expected result: it prints the sample CSV head and pandas dataframe info.

Run the masking smoke test from the project root:

```bash
python -m app.cria.test_security
```

Expected result: it prints the original sentence, a masked sentence with fake
codes, then the original sentence restored by `unmask()`.

Run the Gemini smoke test from the project root after setting `GEMINI_API_KEY`:

```bash
python -m app.cria.test_ai_client
```

Expected result: it first prints a masked version of the question, such as a
fake code in place of `Ahmed`, then prints the final answer after unmasking.

---

## Going to production

- Set a strong, unique `SECRET_KEY`.
- Set `SESSION_COOKIE_SECURE=true` and serve over HTTPS.
- Prefer a dedicated SQL login with least privilege over `sa`.
- Run behind a proper WSGI server instead of the dev server, e.g.:
  ```bash
  pip install waitress
  waitress-serve --port=8000 run:app
  ```
