import logging
from datetime import datetime, timedelta
from itertools import groupby
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.utils.formatting import Bold, Text, as_marked_section
from aiogram.types import Message

import clock
from db import EventRepo, UserRepo
from models import Event

log = logging.getLogger(__name__)

router = Router()

GLYPH = {"done": "✓ ", "now": "> ", "upcoming": "! "}


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    next_event = await event_repo.select_next_event(message.from_user.id, now)
    if not next_event:
        log.info("user %s: /schedule with no upcoming events", message.from_user.id)
        await message.answer("Nothing ahead, /add_events first")
        return
    await send_schedule(message, event_repo, now, next_event.start_dt, next_event.start_dt + timedelta(days=7),
                        with_glyph=False)


@router.message(Command("week"))
async def cmd_week(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    start = day_start(now) - timedelta(days=now.weekday())
    await send_schedule(message, event_repo, now, start, start + timedelta(days=7))


@router.message(Command("today"))
async def cmd_today(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    start = day_start(now)
    await send_schedule(message, event_repo, now, start, start + timedelta(days=1))


@router.message(Command("next"))
async def next_cmd(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    event = await event_repo.select_next_event(message.from_user.id, now)
    if event is None:
        log.info("user %s: /next with no upcoming events", message.from_user.id)
        await message.answer("Nothing ahead, /add_events first")
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
                        start: datetime, end: datetime, with_glyph: bool = True) -> None:
    events = await event_repo.select_events(message.from_user.id, start, end)
    if not events:
        log.info("user %s: schedule request with no events in range", message.from_user.id)
        await message.answer("Nothing scheduled here, /add_events first")
        return
    for section in format_schedule(events, now, with_glyph):
        await message.answer(**section.as_kwargs())


async def get_now(message: Message, user_repo: UserRepo) -> datetime | None:
    assert message.from_user
    tz_str = await user_repo.get_timezone(message.from_user.id)
    if not tz_str:
        log.info("user %s: schedule request with no timezone set", message.from_user.id)
        await message.answer("Send your timetable first: /add_events")
        return None

    return clock.now(tz_str)


def status(e: Event, now: datetime) -> str:
    if e.end_dt <= now:
        return "done"
    if e.start_dt <= now:
        return "now"
    return "upcoming"


def format_time_until(delta: timedelta) -> str:
    total_minutes = -(-int(delta.total_seconds()) // 60)
    days, rem = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


def format_event(e: Event, now: datetime, with_glyph: bool = True) -> Text:
    return Text(
        GLYPH[status(e, now)] if with_glyph else "",
        Bold(f"{e.start_dt:%H:%M}-{e.end_dt:%H:%M}"), " ",
        e.name, f" ({e.type.value})",
    )


def format_next(e: Event, now: datetime) -> Text:
    delta = e.start_dt - now
    header = "Starting now" if delta < timedelta(minutes=1) else f"Next up in {format_time_until(delta)}"
    return Text(
        Bold(header), "\n\n",
        Bold(e.name), "\n",
        f"{e.type.value} - {e.start_dt:%a %d %b}, {e.start_dt:%H:%M}-{e.end_dt:%H:%M}",
    )


def format_section(day: str, day_events: list[Event], now, with_glyph: bool = True) -> Text:
    return as_marked_section(
        Bold(day),
        *[format_event(e, now, with_glyph) for e in day_events],
        marker="",
    )


def format_schedule(events: list[Event], now, with_glyph: bool = True) -> list[Text]:
    return [
        format_section(day, list(day_events), now, with_glyph)
        for day, day_events in groupby(events, key=lambda e: e.day)
    ]
