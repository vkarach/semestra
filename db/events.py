import logging
from datetime import datetime
from uuid import uuid4

from models import Event, EventType


log = logging.getLogger(__name__)


def _row_to_event(row) -> Event:
    return Event(
        id=row[0],
        name=row[1],
        event_type=EventType[row[2]],
        start=datetime.fromisoformat(row[3]),
        end=datetime.fromisoformat(row[4]),
        notified_at=datetime.fromisoformat(row[5]) if row[5] else None,
    )


class EventRepo:
    _INSERT_EVENT = (
        '''
        INSERT INTO events (user_id, import_id, name, type, starts_at, ends_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, name, type, starts_at)
        DO UPDATE SET
            ends_at   = excluded.ends_at,
            import_id = excluded.import_id
        '''
    )
    _DELETE_STALE_EVENT = (
        "DELETE FROM events WHERE user_id = ? AND import_id != ?"
    )
    _DELETE_STALE_FUTURE = (
        "DELETE FROM events WHERE user_id = ? AND import_id != ? AND starts_at > ?"
    )
    _SELECT_EVENTS = (
        "SELECT rowid, name, type, starts_at, ends_at, notified_at FROM events "
        "WHERE user_id = ? AND starts_at >= ? AND starts_at < ? "
        "ORDER BY starts_at"
    )
    _SELECT_NEXT_EVENT = (
        "SELECT rowid, name, type, starts_at, ends_at, notified_at FROM events "
        "WHERE user_id = ? AND starts_at >= ? "
        "ORDER BY starts_at LIMIT 1"
    )
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
            )
            for e in events
        ]

        await self._conn.executemany(self._INSERT_EVENT, rows)
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


    async def mark_notified(self, event_id: int, when: datetime):
        await self._conn.execute(self._MARK_NOTIFIED, (when.isoformat(), event_id))
        await self._conn.commit()


    async def count_events(self) -> int:
        async with self._conn.execute(self._COUNT_EVENTS) as cursor:
            row = await cursor.fetchone()
            return row[0]
