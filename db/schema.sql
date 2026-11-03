CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    timezone       TEXT,
    remind_before  INTEGER,
    start_notice   INTEGER NOT NULL DEFAULT 1,
    digest_at      TEXT,
    digest_sent_on TEXT
);

CREATE TABLE IF NOT EXISTS events (
    user_id     INTEGER NOT NULL,
    import_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,
    starts_at   TEXT NOT NULL,
    ends_at     TEXT NOT NULL,
    notified_at TEXT,
    location    TEXT,
    description TEXT,
    note        TEXT,
    cancelled   INTEGER NOT NULL DEFAULT 0,
    muted       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, name, type, starts_at)
);

CREATE INDEX IF NOT EXISTS idx_events_start ON events(user_id, starts_at);

CREATE TABLE IF NOT EXISTS subjects (
    id      INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name    TEXT NOT NULL,
    alias   TEXT,
    note    TEXT,
    muted   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, name)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_subjects_alias
    ON subjects(user_id, alias COLLATE NOCASE) WHERE alias IS NOT NULL;

CREATE TABLE IF NOT EXISTS series (
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    note       TEXT,
    muted      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (subject_id, type)
);
