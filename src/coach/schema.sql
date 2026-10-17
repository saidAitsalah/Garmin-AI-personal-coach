-- Raw Garmin responses, kept as-is so normalisation can be re-run without re-downloading.
CREATE TABLE IF NOT EXISTS raw_payloads (
    date       TEXT NOT NULL,
    endpoint   TEXT NOT NULL,
    json       TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (date, endpoint)
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    date               TEXT PRIMARY KEY,
    sleep_score        REAL,
    sleep_duration_min INTEGER,
    deep_min           INTEGER,
    rem_min            INTEGER,
    light_min          INTEGER,
    awake_min          INTEGER,
    hrv_overnight_avg  REAL,
    hrv_weekly_avg     REAL,
    hrv_status         TEXT,
    hrv_baseline_low   REAL,
    hrv_baseline_high  REAL,
    rhr                REAL,
    avg_stress         REAL,
    body_battery_wake  REAL,
    body_battery_high  REAL,
    respiration_avg    REAL,
    vo2max             REAL,
    training_readiness REAL,
    readiness_level    TEXT,
    acute_load         REAL,
    chronic_load       REAL,
    load_ratio         REAL,
    steps              INTEGER
);

CREATE TABLE IF NOT EXISTS activities (
    id            INTEGER PRIMARY KEY,
    date          TEXT NOT NULL,
    type          TEXT NOT NULL,      -- gym | swim | run | other
    type_key      TEXT,               -- Garmin's own activity type key
    duration_min  REAL,
    distance_m    REAL,
    avg_hr        REAL,
    training_load REAL,
    aerobic_te    REAL,
    anaerobic_te  REAL
);
CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(date);

CREATE TABLE IF NOT EXISTS journal (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT NOT NULL,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal(date);

CREATE TABLE IF NOT EXISTS plans (
    date           TEXT PRIMARY KEY,
    prompt_version TEXT NOT NULL,
    source         TEXT NOT NULL,     -- llm | fallback
    json           TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    date       TEXT PRIMARY KEY,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    sent_at    TEXT                   -- NULL until actually delivered
);
