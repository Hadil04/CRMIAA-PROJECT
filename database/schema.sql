-- ==========================================================================
-- CRMIAA — Database schema
-- Run this in SQL Server Management Studio (SSMS) or via sqlcmd on the target
-- machine. It creates the CRMIAA database (if missing) and all application
-- tables.
--
-- After running this, create the admin account with a *hashed* password:
--     python manage.py create-admin hadil hadil123 Admin
-- (Do NOT insert the password as plaintext here — the app expects a hash.)
-- ==========================================================================

IF DB_ID('CRMIAA') IS NULL
    CREATE DATABASE CRMIAA;
GO

USE CRMIAA;
GO

-- ---- Users ---------------------------------------------------------------
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
GO

-- ---- Employees -----------------------------------------------------------
-- CRM employee records used by the CRIA module.
-- Excel import: required columns Name, Department, Salary.
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
GO

-- ---- Users.EmployeeId (nullable FK → Employees) -------------------------
-- Links an auto-generated login account back to its source Employee row.
-- Existing rows (e.g. the Admin account) keep EmployeeId = NULL — untouched.
-- Run this block after both tables exist.
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('dbo.Users')
      AND name = 'EmployeeId'
)
BEGIN
    ALTER TABLE dbo.Users
        ADD EmployeeId INT NULL
            CONSTRAINT FK_Users_Employees
            FOREIGN KEY REFERENCES dbo.Employees(Id);
END
GO
