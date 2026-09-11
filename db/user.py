import logging

from models import User

log = logging.getLogger(__name__)


class UserRepo:
    _INSERT_USER = "INSERT INTO users (user_id) VALUES (?) ON CONFLICT DO NOTHING"
    _UPDATE_USER_TIMEZONE = "UPDATE users SET timezone = ? WHERE user_id = ?"
    _GET_USER_TIMEZONE = "SELECT timezone FROM users WHERE user_id = ?"
    _UPDATE_REMIND_BEFORE = "UPDATE users SET remind_before = ? WHERE user_id = ?"
    _LIST_USERS = (
        "SELECT user_id, timezone, remind_before, start_notice FROM users WHERE timezone IS NOT NULL"
    )
    _COUNT_USERS = "SELECT COUNT(*) FROM users"
    _COUNT_USERS_WITH_TIMEZONE = "SELECT COUNT(*) FROM users WHERE timezone IS NOT NULL"

    def __init__(self, conn):
        self._conn = conn


    async def ensure_user(self, user_id: int):
        cursor = await self._conn.execute(self._INSERT_USER, (user_id,))
        await self._conn.commit()
        if cursor.rowcount:
            log.info("registered new user %s", user_id)


    async def update_timezone(self, user_id: int, timezone: str):
        await self._conn.execute(self._UPDATE_USER_TIMEZONE, (timezone, user_id))
        await self._conn.commit()


    async def get_timezone(self, user_id: int):
        async with self._conn.execute(self._GET_USER_TIMEZONE, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row["timezone"] if row else None


    async def set_remind_before(self, user_id: int, minutes: int):
        await self._conn.execute(self._UPDATE_REMIND_BEFORE, (minutes, user_id))
        await self._conn.commit()


    async def count_users(self) -> int:
        async with self._conn.execute(self._COUNT_USERS) as cursor:
            row = await cursor.fetchone()
            return row[0]


    async def count_users_with_timezone(self) -> int:
        async with self._conn.execute(self._COUNT_USERS_WITH_TIMEZONE) as cursor:
            row = await cursor.fetchone()
            return row[0]


    async def list_users(self) -> list[User]:
        async with self._conn.execute(self._LIST_USERS) as cursor:
            rows = await cursor.fetchall()
            return [
                User(r["user_id"], r["timezone"], r["remind_before"], bool(r["start_notice"]))
                for r in rows
            ]
