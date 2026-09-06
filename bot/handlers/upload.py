from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.formatting import Bold, Italic, Text
from aiogram.types import Message

from ics.parser import parse_ics
from db import EventRepo

router = Router()


class Upload(StatesGroup):
    waiting_file = State()


@router.message(Command("add_events"))
async def cmd_today(message: Message, state: FSMContext):
    await state.set_state(Upload.waiting_file)
    content = Text("Send events ", Italic(Bold(".ics")), " file")
    await message.answer(**content.as_kwargs())


@router.message(Upload.waiting_file, F.document)
async def add_events(message: Message, bot: Bot, repo: EventRepo):
    document = message.document
    assert document
    assert message.from_user
    assert document.file_name

    if not document.file_name.lower().endswith("ics"):
        await message.answer("Wrong file type, expected ics")
        return
    elif document.file_size >= 5*1024*1024:
        await message.answer("File is too big")
        return


    buffer = await bot.download(document)
    assert buffer

    events = parse_ics(buffer.read())
    await repo.save_events(message.from_user.id, events)
    await message.answer(f"saved {len(events)} events")


