import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.formatting import Bold, Italic, Text
from aiogram.types import Message

from db import UserRepo, EventRepo
from ics.parser import parse_ics

log = logging.getLogger(__name__)

router = Router()


class Upload(StatesGroup):
    waiting_file = State()


@router.message(Command("add_events"))
async def cmd_add_events(message: Message, state: FSMContext):
    await state.set_state(Upload.waiting_file)
    content = Text("Send events ", Italic(Bold(".ics")), " file")
    await message.answer(**content.as_kwargs())


@router.message(Upload.waiting_file, F.document)
async def add_events(message: Message, bot: Bot, user_repo: UserRepo, event_repo: EventRepo):
    document = message.document
    assert document
    assert message.from_user
    assert document.file_name

    user_id = message.from_user.id
    if not document.file_name.lower().endswith("ics"):
        log.info("user %s: rejected %r, not an ics", user_id, document.file_name)
        await message.answer("Wrong file type, expected ics")
        return
    elif document.file_size >= 5*1024*1024:
        log.info("user %s: rejected %r, too big (%d bytes)", user_id, document.file_name, document.file_size)
        await message.answer("File is too big")
        return


    buffer = await bot.download(document)
    assert buffer

    try:
        parsed = parse_ics(buffer.read())
    except Exception:
        log.exception("user %s: failed to parse %r", user_id, document.file_name)
        await message.answer("Could not parse this ics file")
        return

    await event_repo.save_events(user_id, parsed.events)
    if parsed.timezone is None:
        log.warning("user %s: %r has no usable timezone", user_id, document.file_name)
        await message.answer(f"saved {len(parsed.events)} events, but could not detect timezone")
        return

    await user_repo.update_timezone(user_id, parsed.timezone)
    await message.answer(f"saved {len(parsed.events)} events (timezone {parsed.timezone})")


