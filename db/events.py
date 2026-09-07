from datetime import datetime
from uuid import uuid4

from models import Event, EventType


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
        "SELECT name, type, starts_at, ends_at FROM events WHERE user_id = ? AND 1"
    )


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
        await self._conn.execute(self._DELETE_STALE_EVENT, (user_id, import_id))
        await self._conn.commit()


    async def select_events(self, user_id: int):
        async with self._conn.execute(self._SELECT_EVENTS, (user_id,)) as cursor:
            rows = await cursor.fetchall()
        return [
            Event(
                name=row[0],
                event_type=EventType[row[1]],
                start=datetime.fromisoformat(row[2]),
                end=datetime.fromisoformat(row[3]),
            )
            for row in rows
        ]
