CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    ics_url    TEXT NOT NULL,
    notify_min INTEGER NOT NULL DEFAULT 15,
    last_sync  TEXT
);

CREATE TABLE IF NOT EXISTS events (
    user_id   INTEGER NOT NULL,
    name      TEXT NOT NULL,
    type      TEXT NOT NULL,
    day       TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_start ON events(user_id, starts_at);
