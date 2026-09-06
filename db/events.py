from models import Event


class EventRepo:
    _INSERT_EVENT = (
        "INSERT INTO events (user_id, name, type, day, starts_at, ends_at)"
        " VALUES (?, ?, ?, ?, ?, ?)"
    )
    def __init__(self, conn):
        self._conn = conn


    async def save_events(self, user_id: int, events: list[Event]):
        rows = [
            (
                user_id,
                e.name,
                e.type.name,
                e.day,
                e.start_dt.isoformat(),
                e.end_dt.isoformat(),
            )
            for e in events
        ]

        await self._conn.executemany(self._INSERT_EVENT, rows)
        await self._conn.commit()
