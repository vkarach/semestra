from uuid import uuid4

from models import Event


class EventRepo:
    _INSERT_EVENT = (
        '''
        INSERT INTO events (user_id, import_id, name, type, day, starts_at, ends_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, name, type, starts_at)
        DO UPDATE SET
            day       = excluded.day,
            ends_at   = excluded.ends_at,
            import_id = excluded.import_id
        '''
    )
    _DELETE_STALE_EVENT = (
        "DELETE FROM events WHERE user_id = ? AND import_id != ?"
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
                e.day,
                e.start_dt.isoformat(),
                e.end_dt.isoformat(),
            )
            for e in events
        ]

        await self._conn.executemany(self._INSERT_EVENT, rows)
        await self._conn.execute(self._DELETE_STALE_EVENT, (user_id, import_id))
        await self._conn.commit()
