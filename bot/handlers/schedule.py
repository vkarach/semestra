import logging
from datetime import date, datetime, timedelta
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.formatting import Text

from bot.formatting import (
    NO_EVENTS_AT_ALL,
    day_label,
    format_closest,
    format_exams,
    format_next,
    format_nothing_ahead,
    format_schedule,
    format_section,
)
from bot.handlers.shared import NO_TIMETABLE, day_start, get_now, user_now
from bot.keyboards import DayCb, card_keyboard, day_keyboard, event_list_keyboard
from bot.sending import answer, edit
from db import EventRepo, UserRepo
from models import EventType

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
                        label="ahead", with_status=False)


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
    await send_day(message, user_repo, event_repo, offset=0)


@router.message(Command("tomorrow"))
async def cmd_tomorrow(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    await send_day(message, user_repo, event_repo, offset=1)


@router.callback_query(DayCb.filter())
async def on_day(callback: CallbackQuery, callback_data: DayCb,
                 user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert isinstance(callback.message, Message)
    now = await user_now(user_repo, callback.from_user.id)
    if now is None:
        await callback.answer(NO_TIMETABLE, show_alert=True)
        return
    content, markup = await render_day(event_repo, callback.from_user.id,
                                       date.fromisoformat(callback_data.day), now)
    await edit(callback.message, content, markup)
    await callback.answer()


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
    await answer(message, format_next(event, now), card_keyboard(event))


@router.message(Command("exams"))
async def cmd_exams(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    exams = await event_repo.select_unfinished_of_type(message.from_user.id, EventType.EXAM, now)
    markup = event_list_keyboard(exams) if exams else None
    await message.answer(**format_exams(exams, now).as_kwargs(), reply_markup=markup)


async def send_day(message: Message, user_repo: UserRepo, event_repo: EventRepo, *, offset: int) -> None:
    assert message.from_user
    now = await get_now(message, user_repo)
    if not now:
        return
    day = now.date() + timedelta(days=offset)
    content, markup = await render_day(event_repo, message.from_user.id, day, now)
    await message.answer(**content.as_kwargs(), reply_markup=markup)


async def render_day(event_repo: EventRepo, user_id: int, day: date,
                     now: datetime) -> tuple[Text, InlineKeyboardMarkup]:
    start = datetime.combine(day, datetime.min.time())
    events = await event_repo.select_events(user_id, start, start + timedelta(days=1))
    markup = day_keyboard(day, now.date(), events)
    if events:
        return format_section(day, events, now), markup

    label = day_label(day, now.date())
    closest = await event_repo.select_next_event(user_id, max(now, start))
    if closest is not None:
        return format_closest(closest, now, label), markup
    return await nothing_ahead_content(event_repo, user_id, label), markup


async def send_schedule(message: Message, event_repo: EventRepo, now: datetime,
                        start: datetime, end: datetime, *, label: str,
                        with_status: bool = True) -> None:
    assert message.from_user
    events = await event_repo.select_events(message.from_user.id, start, end)
    if not events:
        log.info("user %s: schedule request with no events in range", message.from_user.id)
        await send_no_events(message, event_repo, now, label)
        return
    for section in format_schedule(events, now, with_status):
        await message.answer(**section.as_kwargs())


async def send_no_events(message: Message, event_repo: EventRepo, now: datetime, label: str) -> None:
    assert message.from_user
    event = await event_repo.select_next_event(message.from_user.id, now)
    if event is None:
        await send_nothing_ahead(message, event_repo, label)
        return
    await message.answer(**format_closest(event, now, label).as_kwargs())


async def nothing_ahead_content(event_repo: EventRepo, user_id: int, label: str | None = None) -> Text:
    if await event_repo.has_events(user_id):
        return format_nothing_ahead(label)
    return NO_EVENTS_AT_ALL


async def send_nothing_ahead(message: Message, event_repo: EventRepo, label: str | None = None) -> None:
    assert message.from_user
    content = await nothing_ahead_content(event_repo, message.from_user.id, label)
    await message.answer(**content.as_kwargs())
