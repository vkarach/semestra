import logging
from itertools import groupby

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.formatting import Bold, Italic, Text, as_marked_section
from aiogram.types import Message

from db import EventRepo

log = logging.getLogger(__name__)

router = Router()


@router.message(Command("show"))
async def cmd_show(message: Message, event_repo: EventRepo):
    assert message.from_user
    events = await event_repo.select_events(message.from_user.id)
    if not events:
        log.info("user %s: /show with no stored events", message.from_user.id)
        await message.answer("Nothing stored yet, /add_events first")
        return

    for day, day_events in groupby(events, key=lambda e: e.day):
        section = as_marked_section(
            Bold(day),
            *[
                Text(
                    Bold(e.name), f" ({e.type.value}) ",
                    f"{e.start_dt:%H:%M}-{e.end_dt:%H:%M}",
                )
                for e in day_events
            ],
            marker="• ",
        )
        await message.answer(**section.as_kwargs())
