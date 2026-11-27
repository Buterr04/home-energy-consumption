-- Household Electricity Consumption Analysis
-- Core business tables and views
-- Run first: sqlite3 app.db < db/01_business.sql
-- db/02_log.sql is intentionally not used by this application.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------------
-- Auth and ownership
-- ---------------------------------------------------------------------------

CREATE TABLE import_batches (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    filename             TEXT NOT NULL,
    imported_at          TEXT NOT NULL DEFAULT (datetime('now')),
    total_rows           INTEGER NOT NULL DEFAULT 0,
    inserted_rows        INTEGER NOT NULL DEFAULT 0,
    rejected_rows        INTEGER NOT NULL DEFAULT 0,
    duplicate_rows       INTEGER NOT NULL DEFAULT 0,
    quality_flagged_rows INTEGER NOT NULL DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'dry_run'))
);

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('user', 'admin')),
    display_name  TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE households (
    id            INTEGER PRIMARY KEY CHECK (id > 0),
    owner_user_id INTEGER,
    display_name  TEXT,
    city          TEXT NOT NULL DEFAULT 'Chengdu',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- A user may own many households; each household has at most one owner.
CREATE INDEX idx_households_owner
    ON households (owner_user_id);

-- ---------------------------------------------------------------------------
-- Appliance dimension and reading fact table
-- ---------------------------------------------------------------------------

CREATE TABLE appliances (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE energy_readings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id     INTEGER NOT NULL,
    appliance_id     INTEGER NOT NULL,
    reading_date     TEXT NOT NULL
        CHECK (reading_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    reading_time     TEXT NOT NULL
        CHECK (reading_time GLOB '[0-2][0-9]:[0-5][0-9]'),
    energy_kwh       REAL NOT NULL CHECK (energy_kwh >= 0),
    outdoor_temp_c   REAL NOT NULL,
    season           TEXT NOT NULL
        CHECK (season IN ('Winter', 'Spring', 'Summer', 'Fall')),
    household_size   INTEGER NOT NULL CHECK (household_size BETWEEN 1 AND 20),
    quality_flag     TEXT NOT NULL DEFAULT 'ok'
        CHECK (quality_flag IN ('ok', 'seasonal_temp_outlier', 'duplicate', 'other')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (household_id, appliance_id, reading_date, reading_time),
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
    FOREIGN KEY (appliance_id) REFERENCES appliances(id) ON DELETE RESTRICT
);

CREATE INDEX idx_readings_home_date
    ON energy_readings (household_id, reading_date);

CREATE INDEX idx_readings_date_appliance
    ON energy_readings (reading_date, appliance_id);

CREATE INDEX idx_readings_quality
    ON energy_readings (quality_flag, reading_date);

-- ---------------------------------------------------------------------------
-- Derived household profile
-- Materialized from energy_readings; safe to rebuild after every import.
-- ---------------------------------------------------------------------------

CREATE TABLE household_profiles (
    household_id  INTEGER PRIMARY KEY,
    size_median   REAL,
    size_mode     INTEGER,
    avg_temp_c    REAL,
    avg_daily_kwh REAL,
    reading_count INTEGER NOT NULL DEFAULT 0,
    first_date    TEXT,
    last_date     TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

CREATE VIEW daily_household_consumption AS
SELECT household_id,
       reading_date,
       SUM(energy_kwh) AS total_kwh,
       COUNT(*)        AS reading_count
FROM energy_readings
GROUP BY household_id, reading_date;

CREATE VIEW user_accessible_households AS
SELECT h.owner_user_id AS user_id,
       h.id           AS household_id
FROM households h
JOIN users u ON u.id = h.owner_user_id
WHERE u.is_active = 1;
