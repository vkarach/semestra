from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.formatting import Bold, Text

from bot.commands import help_content
from db import EventRepo

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, event_repo: EventRepo):
    assert message.from_user
    if await event_repo.has_events(message.from_user.id):
        await message.answer("Semestra on air. /today for the day, /help to see commands.")
        return
    content = Text(
        Bold("Semestra keeps your timetable and reminds you before each class."), "\n\n",
        "Send your .ics timetable to start. At TUKE it is MAIS -> Rozvrh -> iCal export, ",
        "more in /ics_help.",
    )
    await message.answer(**content.as_kwargs())


@router.message(Command("help"))
async def cmd_help(message: Message, is_admin: bool) -> None:
    section = help_content(admin=is_admin)
    await message.answer(**section.as_kwargs())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("Nothing to cancel.")
        return
    await state.clear()
    await message.answer("Cancelled.")
