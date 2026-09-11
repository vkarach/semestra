import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.formatting import Text, Code
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import clock
from db import UserRepo, EventRepo
from ics.parser import parse_ics

log = logging.getLogger(__name__)

router = Router()


class Upload(StatesGroup):
    choosing_mode = State()
    waiting_file = State()


_MODE_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="Replace all", callback_data="import:replace"),
    InlineKeyboardButton(text="Merge", callback_data="import:merge"),
]])


@router.message(Command("add_events"))
async def cmd_add_events(message: Message, state: FSMContext):
    await state.set_state(Upload.choosing_mode)
    await message.answer(
        "Replace the whole timetable or merge into the existing one?",
        reply_markup=_MODE_KB,
    )


@router.callback_query(Upload.choosing_mode, F.data.startswith("import:"))
async def choose_mode(callback: CallbackQuery, state: FSMContext):
    assert isinstance(callback.message, Message)
    replace = callback.data.split(":", 1)[1] == "replace"
    await state.update_data(replace=replace)
    await state.set_state(Upload.waiting_file)
    mode = "Replace" if replace else "Merge"
    content = Text(mode, " mode. Now send the ", Code(".ics"), " file. For help /ics_help")
    await callback.message.edit_text(**content.as_kwargs())
    await callback.answer()


@router.message(Upload.waiting_file, F.document)
async def add_events(message: Message, bot: Bot, state: FSMContext,
                     user_repo: UserRepo, event_repo: EventRepo):
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

    replace = (await state.get_data()).get("replace", False)
    now = clock.now(parsed.timezone) if parsed.timezone else None
    await event_repo.save_events(user_id, parsed.events, replace, now)
    await state.clear()

    verb = "replaced" if replace else "merged"
    if parsed.timezone is None:
        log.warning("user %s: %r has no usable timezone", user_id, document.file_name)
        await message.answer(f"{verb} {len(parsed.events)} events, but could not detect timezone")
        return

    await user_repo.update_timezone(user_id, parsed.timezone)
    await message.answer(f"{verb} {len(parsed.events)} events (timezone {parsed.timezone})")
