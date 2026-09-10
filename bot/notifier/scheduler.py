import logging
from datetime import timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import clock
from db import EventRepo, UserRepo

log = logging.getLogger(__name__)

DEFAULT_REMIND_BEFORE = timedelta(minutes=15)


async def check_reminders(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> None:
    for user in await user_repo.list_users():
        window = timedelta(minutes=user.remind_before) if user.remind_before else DEFAULT_REMIND_BEFORE
        now = clock.now(user.timezone)
        for e in await event_repo.select_events(user.id, now, now + window):
            if e.notified_at and e.notified_at >= e.start_dt - window:
                continue
            mins = round((e.start_dt - now).total_seconds() / 60)
            log.info("reminder user %s: %s in %d min", user.id, e.name, mins)
            await bot.send_message(
                user.id,
                f"{e.name} ({e.type.value}) in {mins} min, starts {e.start_dt:%H:%M}",
            )
            assert e.id
            await event_repo.mark_notified(e.id, now)


async def check_starting(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> None:
    for user in await user_repo.list_users():
        if not user.start_notice:
            continue
        now = clock.now(user.timezone)
        for e in await event_repo.select_events(user.id, now - timedelta(minutes=1),
                                                now + timedelta(minutes=1)):
            if e.notified_at and e.notified_at >= e.start_dt:
                continue
            log.info("start notice user %s: %s", user.id, e.name)
            await bot.send_message(user.id, f"{e.name} ({e.type.value}) now!")
            assert e.id
            await event_repo.mark_notified(e.id, e.start_dt)


def setup_notifier(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_reminders, trigger="interval", minutes=1,
        args=(bot, event_repo, user_repo),
    )
    scheduler.add_job(
        check_starting, trigger="interval", minutes=1,
        args=(bot, event_repo, user_repo),
    )
    return scheduler
