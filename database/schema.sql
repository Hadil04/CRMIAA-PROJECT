-- ==========================================================================
-- CRMIAA — Database schema
-- Run this in SQL Server Management Studio (SSMS) or via sqlcmd on the target
-- machine. It creates the CRMIAA database (if missing) and the Users table.
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
