import logging
from datetime import datetime, timedelta
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import clock
from bot.formatting import (
    NO_EVENTS_AT_ALL,
    format_closest,
    format_next,
    format_nothing_ahead,
    format_schedule,
)
from db import EventRepo, UserRepo

log = logging.getLogger(__name__)

router = Router()


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    next_event = await event_repo.select_next_event(message.from_user.id, now)
    if not next_event:
        log.info("user %s: /schedule with no upcoming events", message.from_user.id)
        await send_nothing_ahead(message, event_repo)
        return
    await send_schedule(message, event_repo, now, next_event.start_dt, next_event.start_dt + timedelta(days=7),
                        label="ahead", with_glyph=False)


@router.message(Command("week"))
async def cmd_week(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    start = day_start(now) - timedelta(days=now.weekday())
    await send_schedule(message, event_repo, now, start, start + timedelta(days=7), label="this week")


@router.message(Command("today"))
async def cmd_today(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    start = day_start(now)
    await send_schedule(message, event_repo, now, start, start + timedelta(days=1), label="today")


@router.message(Command("next"))
async def next_cmd(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    event = await event_repo.select_next_event(message.from_user.id, now)
    if event is None:
        log.info("user %s: /next with no upcoming events", message.from_user.id)
        await send_nothing_ahead(message, event_repo)
        return
    log.info("user %s: /next -> %s at %s", message.from_user.id, event.name, event.start_dt)
    await message.answer(**format_next(event, now).as_kwargs())


@router.message(Command("remind"))
async def cmd_remind(message: Message, command: CommandObject, user_repo: UserRepo) -> None:
    assert message.from_user
    arg = (command.args or "").strip()
    if not arg.isdigit() or not 1 <= int(arg) <= 1440:
        await message.answer("Usage: /remind <minutes>, 1-1440")
        return
    await user_repo.set_remind_before(message.from_user.id, int(arg))
    await message.answer(f"Reminders will arrive {arg} min before each event")


@router.message(Command("start_notice"))
async def cmd_start_notice(message: Message, user_repo: UserRepo) -> None:
    assert message.from_user
    enabled = await user_repo.toggle_start_notice(message.from_user.id)
    await message.answer(f"Start notice is turned {'on' if enabled else 'off'}")


def day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def send_schedule(message: Message, event_repo: EventRepo, now: datetime,
                        start: datetime, end: datetime, *, label: str,
                        with_glyph: bool = True) -> None:
    assert message.from_user
    events = await event_repo.select_events(message.from_user.id, start, end)
    if not events:
        log.info("user %s: schedule request with no events in range", message.from_user.id)
        await send_no_events(message, event_repo, now, label)
        return
    for section in format_schedule(events, now, with_glyph):
        await message.answer(**section.as_kwargs())


async def send_no_events(message: Message, event_repo: EventRepo, now: datetime, label: str) -> None:
    assert message.from_user
    event = await event_repo.select_next_event(message.from_user.id, now)
    if event is None:
        await send_nothing_ahead(message, event_repo, label)
        return
    await message.answer(**format_closest(event, now, label).as_kwargs())


async def send_nothing_ahead(message: Message, event_repo: EventRepo, label: str | None = None) -> None:
    assert message.from_user
    if await event_repo.has_events(message.from_user.id):
        content = format_nothing_ahead(label)
    else:
        content = NO_EVENTS_AT_ALL
    await message.answer(**content.as_kwargs())


async def get_now(message: Message, user_repo: UserRepo) -> datetime | None:
    assert message.from_user
    tz_str = await user_repo.get_timezone(message.from_user.id)
    if not tz_str:
        log.info("user %s: schedule request with no timezone set", message.from_user.id)
        await message.answer("Send your timetable first: /add_events")
        return None

    return clock.now(tz_str)
