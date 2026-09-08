CREATE TABLE IF NOT EXISTS users (
    user_id  INTEGER PRIMARY KEY,
    timezone TEXT
);

CREATE TABLE IF NOT EXISTS events (
    user_id   INTEGER NOT NULL,
    import_id TEXT NOT NULL,
    name      TEXT NOT NULL,
    type      TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at   TEXT NOT NULL,
    UNIQUE (user_id, name, type, starts_at)
);

CREATE INDEX IF NOT EXISTS idx_events_start ON events(user_id, starts_at);
