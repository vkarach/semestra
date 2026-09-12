import logging

from aiogram import Router, F, Bot, BaseMiddleware
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.formatting import Text, Code
from aiogram.types import (
    Message,
    Document,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import clock
from db import UserRepo, EventRepo
from ics.parser import parse_ics

log = logging.getLogger(__name__)

router = Router()

MAX_FILE_SIZE = 5*1024*1024


class Upload(StatesGroup):
    choosing_mode = State()
    waiting_file = State()


_MODE_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Replace all", callback_data="import:replace"),
        InlineKeyboardButton(text="Merge", callback_data="import:merge"),
    ],
    [InlineKeyboardButton(text="Cancel", callback_data="import:cancel")],
])

_CANCEL_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="Cancel", callback_data="import:cancel"),
]])


def _reject_reason(document: Document) -> str | None:
    file_name = document.file_name or ""
    if not file_name.lower().endswith(".ics"):
        return "Wrong file type, expected ics"
    if (document.file_size or 0) >= MAX_FILE_SIZE:
        return "File is too big"
    return None


async def _accept_document(message: Message, document: Document, state: FSMContext) -> bool:
    """Validate an incoming file and remember it until the mode is chosen."""
    assert message.from_user
    reason = _reject_reason(document)
    if reason is not None:
        log.info("user %s: rejected %r (%s)", message.from_user.id, document.file_name, reason)
        await message.answer(reason)
        return False

    await state.update_data(file_id=document.file_id, file_name=document.file_name)
    return True


async def _apply(message: Message, bot: Bot, user_id: int, file_id: str, file_name: str | None,
                 replace: bool, user_repo: UserRepo, event_repo: EventRepo) -> None:
    buffer = await bot.download(file_id)
    assert buffer

    try:
        parsed = parse_ics(buffer.read())
    except Exception:
        log.exception("user %s: failed to parse %r", user_id, file_name)
        await message.answer("Could not parse this ics file")
        return

    now = clock.now(parsed.timezone) if parsed.timezone else None
    await event_repo.save_events(user_id, parsed.events, replace, now)

    verb = "replaced" if replace else "merged"
    if parsed.timezone is None:
        log.warning("user %s: %r has no usable timezone", user_id, file_name)
        await message.answer(f"{verb} {len(parsed.events)} events, but could not detect timezone")
        return

    await user_repo.update_timezone(user_id, parsed.timezone)
    await message.answer(f"{verb} {len(parsed.events)} events (timezone {parsed.timezone})")


@router.message(Command("add_events"))
async def cmd_add_events(message: Message, state: FSMContext):
    await state.set_state(Upload.choosing_mode)
    await state.set_data({})
    await message.answer(
        "Replace the whole timetable or merge into the existing one?",
        reply_markup=_MODE_KB,
    )


@router.message(StateFilter(None, Upload.choosing_mode), F.document)
async def got_file_first(message: Message, state: FSMContext):
    document = message.document
    assert document
    if not await _accept_document(message, document, state):
        return

    await state.set_state(Upload.choosing_mode)
    await message.answer(
        f"Got {document.file_name}. Replace the whole timetable or merge into the existing one?",
        reply_markup=_MODE_KB,
    )


@router.callback_query(Upload.choosing_mode, F.data.startswith("import:"))
async def choose_mode(callback: CallbackQuery, bot: Bot, state: FSMContext,
                      user_repo: UserRepo, event_repo: EventRepo):
    assert isinstance(callback.message, Message)
    assert callback.data
    assert callback.from_user

    choice = callback.data.split(":", 1)[1]
    if choice == "cancel":
        await state.clear()
        await callback.message.edit_text("Upload cancelled.")
        await callback.answer()
        return

    replace = choice == "replace"
    data = await state.get_data()
    file_id = data.get("file_id")

    if file_id is None:
        await state.update_data(replace=replace)
        await state.set_state(Upload.waiting_file)
        mode = "Replace" if replace else "Merge"
        content = Text(mode, " mode. Now send the ", Code(".ics"), " file. For help /ics_help")
        await callback.message.edit_text(**content.as_kwargs(), reply_markup=_CANCEL_KB)
        await callback.answer()
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await state.clear()
    await _apply(callback.message, bot, callback.from_user.id,
                 file_id, data.get("file_name"), replace, user_repo, event_repo)


@router.message(Upload.waiting_file, F.document)
async def add_events(message: Message, bot: Bot, state: FSMContext,
                     user_repo: UserRepo, event_repo: EventRepo):
    document = message.document
    assert document
    assert message.from_user
    if not await _accept_document(message, document, state):
        return

    replace = (await state.get_data()).get("replace", False)
    await state.clear()
    await _apply(message, bot, message.from_user.id,
                 document.file_id, document.file_name, replace, user_repo, event_repo)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("Nothing to cancel.")
        return
    await state.clear()
    await message.answer("Cancelled.")


@router.message(Upload.waiting_file)
async def waiting_file_hint(message: Message):
    content = Text("Send the ", Code(".ics"), " file, or /cancel to stop.")
    await message.answer(**content.as_kwargs())


@router.callback_query(F.data.startswith("import:"))
async def stale_mode(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("This upload is no longer active.")


class ResetUploadMiddleware(BaseMiddleware):
    """Drop a half-finished upload as soon as the user runs another command."""

    _KEEP = ("/add_events", "/cancel")

    async def __call__(self, handler, event, data):
        state: FSMContext | None = data.get("state")
        text = getattr(event, "text", None) or ""
        if state is not None and text.startswith("/") and not text.startswith(self._KEEP):
            current = await state.get_state()
            if current is not None and current.startswith(Upload.__name__):
                log.info("dropping pending upload, user ran %r", text.split()[0])
                await state.clear()
        return await handler(event, data)
