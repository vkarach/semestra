import logging
from datetime import datetime
from uuid import uuid4

from models import Event, EventType


log = logging.getLogger(__name__)


_COLUMNS = (
    "e.rowid, e.name, e.type, e.starts_at, e.ends_at, e.notified_at, "
    "e.location, e.description, e.note, e.cancelled, "
    "j.id, j.alias, j.note, s.note"
)
_FROM = (
    "FROM events e "
    "LEFT JOIN subjects j ON j.user_id = e.user_id AND j.name = e.name "
    "LEFT JOIN series_notes s ON s.subject_id = j.id AND s.type = e.type"
)


def _row_to_event(row) -> Event:
    return Event(
        id=row[0],
        name=row[1],
        event_type=EventType[row[2]],
        start=datetime.fromisoformat(row[3]),
        end=datetime.fromisoformat(row[4]),
        notified_at=datetime.fromisoformat(row[5]) if row[5] else None,
        location=row[6],
        description=row[7],
        note=row[8],
        cancelled=bool(row[9]),
        subject_id=row[10],
        alias=row[11],
        subject_note=row[12],
        series_note=row[13],
    )


class EventRepo:
    _INSERT_EVENT = (
        '''
        INSERT INTO events (user_id, import_id, name, type, starts_at, ends_at, location, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, name, type, starts_at)
        DO UPDATE SET
            ends_at     = excluded.ends_at,
            import_id   = excluded.import_id,
            location    = excluded.location,
            description = excluded.description
        '''
    )
    _INSERT_SUBJECT = "INSERT OR IGNORE INTO subjects (user_id, name) VALUES (?, ?)"
    _DELETE_STALE_EVENT = (
        "DELETE FROM events WHERE user_id = ? AND import_id != ?"
    )
    _DELETE_STALE_FUTURE = (
        "DELETE FROM events WHERE user_id = ? AND import_id != ? AND starts_at > ?"
    )
    _HAS_EVENTS = (
        "SELECT 1 FROM events WHERE user_id = ?"
    )
    _SELECT_EVENTS = (
        f"SELECT {_COLUMNS} {_FROM} "
        "WHERE e.user_id = ? AND e.starts_at >= ? AND e.starts_at < ? "
        "ORDER BY e.starts_at"
    )
    _SELECT_NEXT_EVENT = (
        f"SELECT {_COLUMNS} {_FROM} "
        "WHERE e.user_id = ? AND e.starts_at >= ? AND NOT e.cancelled "
        "ORDER BY e.starts_at LIMIT 1"
    )
    _SELECT_UNFINISHED_OF_TYPE = (
        f"SELECT {_COLUMNS} {_FROM} "
        "WHERE e.user_id = ? AND e.type = ? AND e.ends_at > ? "
        "ORDER BY e.starts_at"
    )
    _SELECT_OF_SUBJECT = (
        f"SELECT {_COLUMNS} {_FROM} "
        "WHERE e.user_id = ? AND j.id = ? "
        "ORDER BY e.starts_at"
    )
    _SELECT_EVENT = (
        f"SELECT {_COLUMNS} {_FROM} WHERE e.user_id = ? AND e.rowid = ?"
    )
    _SET_NOTE = "UPDATE events SET note = ? WHERE user_id = ? AND rowid = ?"
    _SET_CANCELLED = "UPDATE events SET cancelled = ? WHERE user_id = ? AND rowid = ?"
    _MARK_NOTIFIED = "UPDATE events SET notified_at = ? WHERE rowid = ?"
    _COUNT_EVENTS = "SELECT COUNT(*) FROM events"


    def __init__(self, conn):
        self._conn = conn

    async def save_events(self, user_id: int, events: list[Event], replace: bool,
                          now: datetime | None = None):
        if not events:
            return
        import_id = uuid4().hex
        rows = [
            (
                user_id,
                import_id,
                e.name,
                e.type.name,
                e.start_dt.isoformat(),
                e.end_dt.isoformat(),
                e.location,
                e.description,
            )
            for e in events
        ]

        await self._conn.executemany(self._INSERT_EVENT, rows)
        await self._conn.executemany(self._INSERT_SUBJECT,
                                     [(user_id, name) for name in {e.name for e in events}])
        pruned = 0
        if replace:
            if now is not None:
                cursor = await self._conn.execute(
                    self._DELETE_STALE_FUTURE, (user_id, import_id, now.isoformat())
                )
            else:
                cursor = await self._conn.execute(self._DELETE_STALE_EVENT, (user_id, import_id))
            pruned = cursor.rowcount
        await self._conn.commit()
        log.info("user %s: upserted %d events, replace=%s pruned %d",
                 user_id, len(rows), replace, pruned)


    async def has_events(self, user_id: int) -> bool:
        async with self._conn.execute(self._HAS_EVENTS, (user_id, )) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


    async def select_events(self, user_id: int, start: datetime, end: datetime) -> list[Event]:
        params = (user_id, start.isoformat(), end.isoformat())
        async with self._conn.execute(self._SELECT_EVENTS, params) as cursor:
            rows = await cursor.fetchall()
        log.debug("user %s: selected %d events in [%s, %s)", user_id, len(rows), start, end)
        return [_row_to_event(row) for row in rows]


    async def select_next_event(self, user_id: int, start: datetime) -> Event | None:
        params = (user_id, start.isoformat())
        async with self._conn.execute(self._SELECT_NEXT_EVENT, params) as cursor:
            row = await cursor.fetchone()
        event = _row_to_event(row) if row else None
        log.debug("user %s: next event after %s -> %s", user_id, start,
                  event.name if event else "none")
        return event


    async def select_unfinished_of_type(self, user_id: int, event_type: EventType,
                                        now: datetime) -> list[Event]:
        params = (user_id, event_type.name, now.isoformat())
        async with self._conn.execute(self._SELECT_UNFINISHED_OF_TYPE, params) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_event(row) for row in rows]


    async def select_of_subject(self, user_id: int, subject_id: int) -> list[Event]:
        async with self._conn.execute(self._SELECT_OF_SUBJECT, (user_id, subject_id)) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_event(row) for row in rows]


    async def get_event(self, user_id: int, event_id: int) -> Event | None:
        async with self._conn.execute(self._SELECT_EVENT, (user_id, event_id)) as cursor:
            row = await cursor.fetchone()
        return _row_to_event(row) if row else None


    async def set_note(self, user_id: int, event_id: int, note: str | None):
        await self._conn.execute(self._SET_NOTE, (note, user_id, event_id))
        await self._conn.commit()


    async def set_cancelled(self, user_id: int, event_id: int, cancelled: bool):
        await self._conn.execute(self._SET_CANCELLED, (int(cancelled), user_id, event_id))
        await self._conn.commit()


    async def mark_notified(self, event_id: int, when: datetime):
        await self._conn.execute(self._MARK_NOTIFIED, (when.isoformat(), event_id))
        await self._conn.commit()


    async def count_events(self) -> int:
        async with self._conn.execute(self._COUNT_EVENTS) as cursor:
            row = await cursor.fetchone()
            return row[0]
