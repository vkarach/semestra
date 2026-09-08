import logging


log = logging.getLogger(__name__)


class UserRepo:
    _INSERT_USER = "INSERT INTO users (user_id) VALUES (?) ON CONFLICT DO NOTHING"
    _UPDATE_USER_TIMEZONE = "UPDATE users SET timezone = ? WHERE user_id = ?"
    _GET_USER_TIMEZONE = "SELECT timezone FROM users WHERE user_id = ?"

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
