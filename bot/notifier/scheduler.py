import logging
from datetime import datetime, time, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.formatting import Text
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import clock
from bot.formatting import format_digest, format_reminder, format_start_notice, merged_note
from bot.keyboards import links_keyboard
from bot.sending import send
from db import EventRepo, UserRepo
from models import DEFAULT_REMIND_MINUTES, Event

log = logging.getLogger(__name__)

DIGEST_GRACE = timedelta(minutes=30)


async def check_reminders(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> None:
    for user in await user_repo.list_users():
        if user.remind_before == 0:
            continue
        assert user.timezone
        window = timedelta(minutes=user.remind_before or DEFAULT_REMIND_MINUTES)
        now = clock.now(user.timezone)
        for e in await event_repo.select_events(user.id, now, now + window):
            if _quiet(e) or (e.notified_at and e.notified_at >= e.start_dt - window):
                continue
            mins = round((e.start_dt - now).total_seconds() / 60)
            log.info("reminder user %s: %s in %d min", user.id, e.name, mins)
            if await _alert(bot, user.id, e, format_reminder(e, mins)):
                assert e.id
                await event_repo.mark_notified(e.id, now)


async def check_starting(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> None:
    for user in await user_repo.list_users():
        if not user.start_notice:
            continue
        assert user.timezone
        now = clock.now(user.timezone)
        for e in await event_repo.select_events(user.id, now - timedelta(minutes=1),
                                                now + timedelta(minutes=1)):
            if _quiet(e) or (e.notified_at and e.notified_at >= e.start_dt):
                continue
            log.info("start notice user %s: %s", user.id, e.name)
            if await _alert(bot, user.id, e, format_start_notice(e)):
                assert e.id
                await event_repo.mark_notified(e.id, e.start_dt)


def _quiet(e: Event) -> bool:
    return e.cancelled or e.silenced_by is not None


async def _deliver(bot: Bot, user_id: int, content: Text,
                   markup: InlineKeyboardMarkup | None = None) -> bool:
    try:
        await send(bot, user_id, content, markup)
    except TelegramForbiddenError:
        log.warning("user %s: blocked the bot, notification dropped", user_id)
        return False
    except TelegramAPIError:
        log.exception("user %s: could not deliver a notification", user_id)
        return False
    return True


async def _alert(bot: Bot, user_id: int, e: Event, content: Text) -> bool:
    return await _deliver(bot, user_id, content, links_keyboard(merged_note(e)))


async def check_digest(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> None:
    for user in await user_repo.list_users():
        if not user.digest_at:
            continue
        assert user.timezone
        now = clock.now(user.timezone)
        today = now.date()
        if user.digest_sent_on == today.isoformat():
            continue
        due = datetime.combine(today, time.fromisoformat(user.digest_at))
        if not due <= now < due + DIGEST_GRACE:
            continue
        start = datetime.combine(today, time.min)
        events = await event_repo.select_events(user.id, start, start + timedelta(days=1))
        if any(not e.cancelled for e in events):
            log.info("digest user %s: %d events", user.id, len(events))
            if not await _deliver(bot, user.id, format_digest(today, events, now)):
                continue
        await user_repo.mark_digest_sent(user.id, today)


def setup_notifier(bot: Bot, event_repo: EventRepo, user_repo: UserRepo) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    for job in (check_reminders, check_starting, check_digest):
        scheduler.add_job(
            job, trigger="interval", minutes=1,
            args=(bot, event_repo, user_repo),
        )
    return scheduler
