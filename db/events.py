import logging
from datetime import datetime
from uuid import uuid4

from models import Event, EventType


log = logging.getLogger(__name__)


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
    _SELECT_EVENTS = (
        "SELECT rowid, name, type, starts_at, ends_at, notified_at FROM events "
        "WHERE user_id = ? AND starts_at >= ? AND starts_at < ? "
        "ORDER BY starts_at"
    )
    _MARK_NOTIFIED = "UPDATE events SET notified_at = ? WHERE rowid = ?"


    def __init__(self, conn):
        self._conn = conn

    async def save_events(self, user_id: int, events: list[Event]):
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
        cursor = await self._conn.execute(self._DELETE_STALE_EVENT, (user_id, import_id))
        await self._conn.commit()
        log.info("user %s: upserted %d events, pruned %d stale", user_id, len(rows), cursor.rowcount)


    async def select_events(self, user_id: int, start: datetime, end: datetime):
        params = (user_id, start.isoformat(), end.isoformat())
        async with self._conn.execute(self._SELECT_EVENTS, params) as cursor:
            rows = await cursor.fetchall()
        log.debug("user %s: selected %d events in [%s, %s)", user_id, len(rows), start, end)
        return [
            Event(
                id=row[0],
                name=row[1],
                event_type=EventType[row[2]],
                start=datetime.fromisoformat(row[3]),
                end=datetime.fromisoformat(row[4]),
                notified_at=datetime.fromisoformat(row[5]) if row[5] else None,
            )
            for row in rows
        ]

    async def mark_notified(self, event_id: int, when: datetime):
        await self._conn.execute(self._MARK_NOTIFIED, (when.isoformat(), event_id))
        await self._conn.commit()
