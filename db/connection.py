import logging
import aiosqlite

from pathlib import Path


log = logging.getLogger(__name__)

DB_DIR = Path(__file__).parent.parent / "data"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DB_PATH = DB_DIR / "semestra.db"


_MIGRATIONS = (
    ("users", "remind_before", "INTEGER"),
    ("events", "notified_at", "TEXT"),
    ("users", "start_notice", "INTEGER NOT NULL DEFAULT 1"),
    ("users", "digest_at", "TEXT"),
    ("users", "digest_sent_on", "TEXT"),
    ("events", "location", "TEXT"),
    ("events", "description", "TEXT"),
    ("events", "note", "TEXT"),
    ("events", "cancelled", "INTEGER NOT NULL DEFAULT 0"),
    ("events", "muted", "INTEGER NOT NULL DEFAULT 0"),
    ("subjects", "muted", "INTEGER NOT NULL DEFAULT 0"),
)


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    query = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?"
    async with conn.execute(query, (table,)) as cursor:
        return await cursor.fetchone() is not None


async def _migrate(conn: aiosqlite.Connection) -> None:
    for table, column, decl in _MIGRATIONS:
        async with conn.execute(f"PRAGMA table_info({table})") as cursor:
            existing = {row[1] for row in await cursor.fetchall()}
        if column not in existing:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            log.info("migrated: added %s.%s", table, column)
    if await _table_exists(conn, "series_notes"):
        await conn.execute(
            "INSERT OR IGNORE INTO series (subject_id, type, note) "
            "SELECT subject_id, type, note FROM series_notes"
        )
        await conn.execute("DROP TABLE series_notes")
        log.info("migrated: series_notes -> series")
    cursor = await conn.execute(
        "INSERT OR IGNORE INTO subjects (user_id, name) SELECT DISTINCT user_id, name FROM events"
    )
    if cursor.rowcount:
        log.info("migrated: backfilled %d subjects", cursor.rowcount)


async def connect() -> aiosqlite.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    await _migrate(conn)
    await conn.commit()
    log.info("connected to %s", DB_PATH)
    return conn
