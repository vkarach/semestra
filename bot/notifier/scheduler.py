import logging
from datetime import timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import clock
from db import EventRepo, UserRepo

log = logging.getLogger(__name__)

DEFAULT_REMIND_BEFORE = timedelta(minutes=15)


async def check_reminders(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> None:
    for user_id, tz, remind_min in await user_repo.list_users():
        window = timedelta(minutes=remind_min) if remind_min else DEFAULT_REMIND_BEFORE
        now = clock.now(tz)
        for e in await event_repo.select_events(user_id, now, now + window):
            if e.notified_at and e.notified_at >= e.start_dt - window:
                continue
            mins = round((e.start_dt - now).total_seconds() / 60)
            log.info("reminder user %s: %s in %d min", user_id, e.name, mins)
            await bot.send_message(
                user_id,
                f"{e.name} ({e.type.value}) in {mins} min, starts {e.start_dt:%H:%M}",
            )
            assert e.id
            await event_repo.mark_notified(e.id, now)


def setup_notifier(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_reminders, trigger="interval", minutes=1,
        args=(bot, event_repo, user_repo),
    )
    return scheduler
