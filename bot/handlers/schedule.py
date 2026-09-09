import logging
from datetime import datetime
from itertools import groupby
from zoneinfo import ZoneInfo
from aiogram import Router
from aiogram.filters import Command
from aiogram.utils.formatting import Bold, Text, as_marked_section
from aiogram.types import Message

from db import EventRepo, UserRepo
from models import Event

log = logging.getLogger(__name__)

router = Router()

GLYPH = {"done": " ✓", "now": " >", "upcoming": " !"}


@router.message(Command("week"))
async def cmd_week(message: Message, user_repo: UserRepo, event_repo: EventRepo):
    assert message.from_user
    events = await get_events(message, event_repo)
    if not events:
        return
    now = await get_timezone(message, user_repo)
    if not now:
        return

    for section in format_schedule(events, now):
        await message.answer(**section.as_kwargs())


@router.message(Command("today"))
async def cmd_today(message: Message, user_repo: UserRepo, event_repo: EventRepo):
    assert message.from_user
    events = await get_events(message, event_repo)
    if not events:
        return

    now = await get_timezone(message, user_repo)
    if not now:
        return
    today = [e for e in events if e.start_dt.weekday() == now.weekday()]
    for section in format_schedule(today, now):
        await message.answer(**section.as_kwargs())


async def get_events(message, event_repo: EventRepo) -> list[Event]:
    events = await event_repo.select_events(message.from_user.id)
    if not events:
        log.info("user %s: schedule request with no stored events", message.from_user.id)
        await message.answer("Nothing stored yet, /add_events first")
    return events


async def get_timezone(message: Message, user_repo: UserRepo)-> datetime | None:
    assert message.from_user
    tz_str = await user_repo.get_timezone(message.from_user.id)
    if not tz_str:
        log.info("user %s: with no timezone", message.from_user.id)
        await message.answer("No timezone :( contact developer @karachv")
        return None

    return datetime.now(ZoneInfo(tz_str)).replace(tzinfo=None)


def status(e: Event, now: datetime) -> str:
    start = (e.start_dt.weekday(), e.start_dt.time())
    end = (e.start_dt.weekday(), e.end_dt.time())
    cur = (now.weekday(), now.time())
    if end <= cur:
        return "done"
    if start <= cur:
        return "now"
    return "upcoming"


def format_section(day: str, day_events: list[Event], now) -> Text:
    return as_marked_section(
        Bold(day),
        *[
            Text(
                Bold(e.name), f" ({e.type.value}) ",
                f"{e.start_dt:%H:%M}-{e.end_dt:%H:%M}",
                GLYPH[status(e, now)]
            )
            for e in day_events
        ],
        marker="- ",
    )


def format_schedule(events: list[Event], now) -> list[Text]:
    return [
        format_section(day, list(day_events), now)
        for day, day_events in groupby(events, key=lambda e: e.day)
    ]
