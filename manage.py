"""
CRMIAA management CLI.

Small administrative tasks that talk to the database using the app's own
configuration (`.env`). Run from the project root with the virtualenv active.

Commands:
    python manage.py test-db
        Check the database connection and show which server/db you're on.

    python manage.py init-db
        Create the `Users` table if it doesn't exist.

    python manage.py init-employees-table
        Create the `Employees` table (CRIA data source) if it doesn't exist.

    python manage.py create-admin [username] [password] [role]
        Create OR update an admin account with a securely hashed password.
        Defaults: username=hadil, password=hadil123, role=Admin.

    python manage.py list-users
        List the accounts currently in the Users table.

    python manage.py list-employees
        List the rows currently in the Employees table.
"""
import sys

import pyodbc
from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_connection

# Idempotent table creation (no CREATE DATABASE / GO batches — pyodbc-friendly).
_CREATE_USERS_TABLE = """
IF OBJECT_ID('dbo.Users', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Users (
        Id           INT IDENTITY(1,1) CONSTRAINT PK_Users PRIMARY KEY,
        Username     NVARCHAR(100)  NOT NULL,
        PasswordHash NVARCHAR(255)  NOT NULL,
        Role         NVARCHAR(50)   NOT NULL CONSTRAINT DF_Users_Role     DEFAULT ('User'),
        IsActive     BIT            NOT NULL CONSTRAINT DF_Users_IsActive  DEFAULT (1),
        CreatedAt    DATETIME2      NOT NULL CONSTRAINT DF_Users_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_Users_Username UNIQUE (Username)
    );
END
"""

_CREATE_EMPLOYEES_TABLE = """
IF OBJECT_ID('dbo.Employees', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Employees (
        Id           INT IDENTITY(1,1) CONSTRAINT PK_Employees PRIMARY KEY,
        Name         NVARCHAR(100) NOT NULL,
        Department   NVARCHAR(100) NOT NULL,
        Salary       INT           NOT NULL,
        CreatedAt    DATETIME2     NOT NULL CONSTRAINT DF_Employees_CreatedAt DEFAULT (SYSUTCDATETIME())
    );
END
"""


def cmd_test_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT @@SERVERNAME, DB_NAME(), SUSER_SNAME()")
        server, db, login = cur.fetchone()
        print("Connection OK")
        print(f"  Server : {server}")
        print(f"  Database: {db}")
        print(f"  Login  : {login}")
        try:
            cur.execute("SELECT COUNT(*) FROM Users")
            print(f"  Users table: {cur.fetchone()[0]} row(s)")
        except pyodbc.Error:
            print("  Users table: NOT FOUND (run: python manage.py init-db)")


def cmd_init_db():
    with get_connection() as conn:
        conn.cursor().execute(_CREATE_USERS_TABLE)
        conn.commit()
    print("Users table is ready.")


def cmd_init_employees_table():
    with get_connection() as conn:
        conn.cursor().execute(_CREATE_EMPLOYEES_TABLE)
        conn.commit()
    print("Employees table is ready.")


def cmd_create_admin(username="hadil", password="hadil123", role="Admin"):
    password_hash = generate_password_hash(password)  # pbkdf2:sha256 by default
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT Id FROM Users WHERE Username = ?", username)
        exists = cur.fetchone() is not None

        if exists:
            cur.execute(
                "UPDATE Users SET PasswordHash = ?, Role = ?, IsActive = 1 "
                "WHERE Username = ?",
                password_hash, role, username,
            )
            action = "updated"
        else:
            cur.execute(
                "INSERT INTO Users (Username, PasswordHash, Role, IsActive) "
                "VALUES (?, ?, ?, 1)",
                username, password_hash, role,
            )
            action = "created"
        conn.commit()
    print(f"Admin account '{username}' {action} (role={role}).")


def cmd_list_users():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT Id, Username, Role, IsActive, CreatedAt FROM Users ORDER BY Id"
        )
        rows = cur.fetchall()
    if not rows:
        print("No users found.")
        return
    print(f"{'Id':<4} {'Username':<20} {'Role':<12} {'Active':<7} CreatedAt")
    for r in rows:
        print(f"{r[0]:<4} {r[1]:<20} {r[2]:<12} {str(bool(r[3])):<7} {r[4]}")


def cmd_list_employees():
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT Id, Name, Department, Salary, CreatedAt "
                "FROM Employees ORDER BY Id"
            )
            rows = cur.fetchall()
        except pyodbc.Error:
            print("Employees table not found — run: python manage.py init-employees-table")
            return
    if not rows:
        print("No employees found.")
        return
    print(f"{'Id':<4} {'Name':<20} {'Department':<18} {'Salary':>10}  CreatedAt")
    for r in rows:
        print(f"{r[0]:<4} {r[1]:<20} {r[2]:<18} {str(r[3]):>10}  {r[4]}")


COMMANDS = {
    "test-db":               cmd_test_db,
    "init-db":               cmd_init_db,
    "init-employees-table":  cmd_init_employees_table,
    "create-admin":          cmd_create_admin,
    "list-users":            cmd_list_users,
    "list-employees":        cmd_list_employees,
}


def main(argv):
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        print("Available commands:", ", ".join(COMMANDS))
        return 1

    command, *rest = argv
    app = create_app()
    with app.app_context():
        try:
            COMMANDS[command](*rest)
        except pyodbc.Error as exc:
            print("DATABASE ERROR:", exc)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
