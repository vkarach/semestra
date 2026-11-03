import logging
from datetime import date

from models import User

log = logging.getLogger(__name__)


def _row_to_user(r) -> User:
    return User(r["user_id"], r["timezone"], r["remind_before"], bool(r["start_notice"]),
                r["digest_at"], r["digest_sent_on"])


class UserRepo:
    _INSERT_USER = "INSERT INTO users (user_id) VALUES (?) ON CONFLICT DO NOTHING"

    _UPDATE_USER_TIMEZONE = "UPDATE users SET timezone = ? WHERE user_id = ?"
    _UPDATE_REMIND_BEFORE = "UPDATE users SET remind_before = ? WHERE user_id = ?"
    _TOGGLE_START_NOTICE = (
        "UPDATE users SET start_notice = NOT start_notice WHERE user_id = ? RETURNING start_notice"
    )

    _UPDATE_DIGEST_AT = "UPDATE users SET digest_at = ? WHERE user_id = ?"
    _UPDATE_DIGEST_SENT_ON = "UPDATE users SET digest_sent_on = ? WHERE user_id = ?"

    _GET_USER_TIMEZONE = "SELECT timezone FROM users WHERE user_id = ?"

    _USER_COLUMNS = "user_id, timezone, remind_before, start_notice, digest_at, digest_sent_on"
    _GET_USER = f"SELECT {_USER_COLUMNS} FROM users WHERE user_id = ?"
    _LIST_USERS = f"SELECT {_USER_COLUMNS} FROM users WHERE timezone IS NOT NULL"

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


    async def toggle_start_notice(self, user_id: int) -> bool:
        async with self._conn.execute(self._TOGGLE_START_NOTICE, (user_id,)) as cursor:
            row = await cursor.fetchone()
        await self._conn.commit()
        return bool(row["start_notice"])


    async def set_remind_before(self, user_id: int, minutes: int):
        await self._conn.execute(self._UPDATE_REMIND_BEFORE, (minutes, user_id))
        await self._conn.commit()


    async def set_digest_at(self, user_id: int, digest_at: str | None):
        await self._conn.execute(self._UPDATE_DIGEST_AT, (digest_at, user_id))
        await self._conn.commit()


    async def mark_digest_sent(self, user_id: int, day: date):
        await self._conn.execute(self._UPDATE_DIGEST_SENT_ON, (day.isoformat(), user_id))
        await self._conn.commit()


    async def get_user(self, user_id: int) -> User | None:
        async with self._conn.execute(self._GET_USER, (user_id,)) as cursor:
            row = await cursor.fetchone()
        return _row_to_user(row) if row else None


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
            return [_row_to_user(r) for r in rows]
