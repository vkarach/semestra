import logging
from datetime import datetime

from aiogram.types import Message

import clock
from db import UserRepo

log = logging.getLogger(__name__)

NO_TIMETABLE = "Send your timetable first: /add_events"


def day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def user_now(user_repo: UserRepo, user_id: int) -> datetime | None:
    tz_str = await user_repo.get_timezone(user_id)
    return clock.now(tz_str) if tz_str else None


async def get_now(message: Message, user_repo: UserRepo) -> datetime | None:
    assert message.from_user
    now = await user_now(user_repo, message.from_user.id)
    if now is None:
        log.info("user %s: schedule request with no timezone set", message.from_user.id)
        await message.answer(NO_TIMETABLE)
    return now
