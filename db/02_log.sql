-- Household Electricity Consumption Analysis
-- Import audit, pretrained model registry, and inference history
-- Run after db/01_business.sql: sqlite3 app.db < db/02_log.sql

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Import audit and data quality
-- ---------------------------------------------------------------------------

CREATE TABLE import_batches (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    filename             TEXT NOT NULL,
    file_hash            TEXT,
    imported_at          TEXT NOT NULL DEFAULT (datetime('now')),
    total_rows           INTEGER NOT NULL DEFAULT 0,
    inserted_rows        INTEGER NOT NULL DEFAULT 0,
    rejected_rows        INTEGER NOT NULL DEFAULT 0,
    duplicate_rows       INTEGER NOT NULL DEFAULT 0,
    quality_flagged_rows INTEGER NOT NULL DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    error_message        TEXT
);

CREATE TABLE import_errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch_id INTEGER NOT NULL,
    row_number      INTEGER NOT NULL,
    error_code      TEXT NOT NULL,
    message         TEXT,
    raw_data        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (import_batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
);

CREATE INDEX idx_import_errors_batch
    ON import_errors (import_batch_id, row_number);

-- ---------------------------------------------------------------------------
-- Pretrained model registry and inference audit
-- The application loads a trained artifact and only performs inference.
-- Training and evaluation happen outside the FastAPI service.
-- ---------------------------------------------------------------------------

CREATE TABLE model_versions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    version       TEXT NOT NULL UNIQUE,
    trained_at    TEXT NOT NULL DEFAULT (datetime('now')),
    train_start   TEXT,
    train_end     TEXT,
    mae           REAL,
    rmse          REAL,
    r2            REAL,
    feature_set   TEXT,
    artifact_path TEXT NOT NULL
);

CREATE TABLE predictions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id     INTEGER NOT NULL,
    household_id         INTEGER NOT NULL,
    appliance_id         INTEGER,
    created_by_user_id   INTEGER,
    target_month         INTEGER NOT NULL CHECK (target_month BETWEEN 1 AND 12),
    input_household_size INTEGER NOT NULL CHECK (input_household_size BETWEEN 1 AND 20),
    predicted_avg_daily_kwh REAL NOT NULL CHECK (predicted_avg_daily_kwh >= 0),
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
    FOREIGN KEY (appliance_id) REFERENCES appliances(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_predictions_household_month
    ON predictions (household_id, target_month);
