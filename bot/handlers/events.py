import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.formatting import format_note_prompt
from bot.handlers.cards import event_card
from bot.handlers.prompts import Target, start_prompt
from bot.keyboards import EventCb
from bot.sending import answer, edit
from db import EventRepo, UserRepo

log = logging.getLogger(__name__)

router = Router()

GONE = "This event is no longer in your timetable"


@router.callback_query(EventCb.filter(F.action.in_({"open", "back"})))
async def on_open(callback: CallbackQuery, callback_data: EventCb,
                  user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert isinstance(callback.message, Message)
    card = await event_card(event_repo, user_repo, callback.from_user.id, callback_data.id)
    if card is None:
        await callback.answer(GONE, show_alert=True)
        return
    if callback_data.action == "back":
        await edit(callback.message, *card)
    else:
        await answer(callback.message, *card)
    await callback.answer()


@router.callback_query(EventCb.filter(F.action == "note"))
async def on_note(callback: CallbackQuery, callback_data: EventCb, state: FSMContext,
                  event_repo: EventRepo) -> None:
    event = await event_repo.get_event(callback.from_user.id, callback_data.id)
    if event is None:
        await callback.answer(GONE, show_alert=True)
        return
    scope = f"{event.title} ({event.type.value}) on {event.start_dt:%a %d %b %H:%M} only"
    target = Target(kind="event", origin="event", origin_id=callback_data.id,
                    event_id=callback_data.id)
    await start_prompt(callback, state, target, format_note_prompt(scope, event.note),
                       has_current=bool(event.note))


@router.callback_query(EventCb.filter(F.action == "cancel"))
async def on_cancel_toggle(callback: CallbackQuery, callback_data: EventCb,
                           user_repo: UserRepo, event_repo: EventRepo) -> None:
    assert isinstance(callback.message, Message)
    user_id = callback.from_user.id
    event = await event_repo.get_event(user_id, callback_data.id)
    if event is None:
        await callback.answer(GONE, show_alert=True)
        return
    await event_repo.set_cancelled(user_id, callback_data.id, not event.cancelled)
    log.info("user %s: event %s cancelled=%s", user_id, event.id, not event.cancelled)
    card = await event_card(event_repo, user_repo, user_id, callback_data.id)
    if card is not None:
        await edit(callback.message, *card)
    await callback.answer("Restored" if event.cancelled else "Marked cancelled")
