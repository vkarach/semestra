import logging
from dataclasses import asdict, dataclass

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Text

import notes
from bot.handlers.cards import Card, event_card, subject_card
from bot.keyboards import PromptCb, prompt_keyboard
from bot.sending import answer, edit
from db import AliasTaken, EventRepo, SubjectRepo, UserRepo
from models import EventType

log = logging.getLogger(__name__)

router = Router()

ALIAS_MAX_LEN = 24


class Prompt(StatesGroup):
    text = State()


@dataclass
class Target:
    kind: str
    origin: str
    origin_id: int
    event_id: int = 0
    subject_id: int = 0
    type: str = ""


async def start_prompt(callback: CallbackQuery, state: FSMContext, target: Target,
                       content: Text, has_current: bool) -> None:
    assert isinstance(callback.message, Message)
    await state.set_state(Prompt.text)
    await state.set_data({**asdict(target), "prompt_id": callback.message.message_id})
    await edit(callback.message, content, prompt_keyboard(has_current))
    await callback.answer()


async def _origin_card(target: Target, user_id: int, event_repo: EventRepo,
                       subject_repo: SubjectRepo, user_repo: UserRepo) -> Card | None:
    if target.origin == "event":
        return await event_card(event_repo, user_repo, user_id, target.origin_id)
    return await subject_card(subject_repo, user_id, target.origin_id)


async def _store(target: Target, user_id: int, value: str | None,
                 event_repo: EventRepo, subject_repo: SubjectRepo) -> None:
    match target.kind:
        case "event":
            await event_repo.set_note(user_id, target.event_id, value)
        case "series":
            await subject_repo.set_series_note(user_id, target.subject_id,
                                               EventType[target.type], value)
        case "subject":
            await subject_repo.set_note(user_id, target.subject_id, value)
        case "alias":
            await subject_repo.set_alias(user_id, target.subject_id, value)
    log.info("user %s: %s %s", user_id, "set" if value else "cleared", target)


def _validate(kind: str, text: str) -> str:
    if kind != "alias":
        return notes.normalize(text)
    alias = text.strip()
    if "\n" in alias or not 1 <= len(alias) <= ALIAS_MAX_LEN:
        raise notes.NoteError(f"A shortcut is one line of 1-{ALIAS_MAX_LEN} characters")
    return alias


async def _pending(state: FSMContext) -> tuple[Target, int] | None:
    if await state.get_state() != Prompt.text:
        return None
    data = await state.get_data()
    prompt_id = data.pop("prompt_id")
    return Target(**data), prompt_id


@router.callback_query(PromptCb.filter())
async def on_prompt_button(callback: CallbackQuery, callback_data: PromptCb, state: FSMContext,
                           event_repo: EventRepo, subject_repo: SubjectRepo,
                           user_repo: UserRepo) -> None:
    assert isinstance(callback.message, Message)
    pending = await _pending(state)
    if pending is None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("This edit is no longer active")
        return
    target, _ = pending
    user_id = callback.from_user.id
    await state.clear()
    if callback_data.action == "clear":
        await _store(target, user_id, None, event_repo, subject_repo)
    card = await _origin_card(target, user_id, event_repo, subject_repo, user_repo)
    if card is not None:
        await edit(callback.message, *card)
    await callback.answer("Cleared" if callback_data.action == "clear" else None)


@router.message(Prompt.text, F.text)
async def got_text(message: Message, bot: Bot, state: FSMContext, event_repo: EventRepo,
                   subject_repo: SubjectRepo, user_repo: UserRepo) -> None:
    assert message.from_user and message.text
    pending = await _pending(state)
    assert pending
    target, prompt_id = pending
    user_id = message.from_user.id

    try:
        value = _validate(target.kind, message.text)
        await _store(target, user_id, value, event_repo, subject_repo)
    except notes.NoteError as e:
        await message.answer(f"{e}. Send it again, or /cancel.")
        return
    except AliasTaken:
        await message.answer("Another subject already uses this shortcut. Pick a different one.")
        return
    await state.clear()

    try:
        await bot.delete_message(message.chat.id, prompt_id)
    except TelegramBadRequest:
        log.debug("user %s: could not delete the prompt", user_id)
    card = await _origin_card(target, user_id, event_repo, subject_repo, user_repo)
    if card is not None:
        await answer(message, *card)


@router.message(Prompt.text)
async def prompt_hint(message: Message) -> None:
    await message.answer("Send it as text, or /cancel to stop.")
