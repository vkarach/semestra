import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Bold, Text

from bot.formatting import format_alias_prompt, format_mutes, format_note_prompt
from bot.handlers.cards import subject_card, subjects_list
from bot.handlers.prompts import Target, start_prompt
from bot.handlers.shared import user_now
from bot.keyboards import (
    CLASSES_PAGE, SubjectCb, classes_keyboard, mutes_keyboard, subjects_keyboard,
)
from bot.sending import answer, edit
from db import EventRepo, SubjectRepo, UserRepo
from models import TYPE_PLURAL, EventType

log = logging.getLogger(__name__)

router = Router()

GONE = "This subject is no longer in your timetable"


@router.message(Command("subjects"))
async def cmd_subjects(message: Message, command: CommandObject, subject_repo: SubjectRepo) -> None:
    assert message.from_user
    user_id = message.from_user.id
    query = (command.args or "").strip()
    if not query:
        await answer(message, *await subjects_list(subject_repo, user_id))
        return

    found = await subject_repo.find(user_id, query)
    if len(found) == 1:
        card = await subject_card(subject_repo, user_id, found[0].id)
        assert card
        await answer(message, *card)
        return
    if found:
        await answer(message, Text(Bold(f"Subjects matching \"{query}\"")), subjects_keyboard(found))
        return
    content, markup = await subjects_list(subject_repo, user_id)
    await answer(message, Text(f"Nothing matches \"{query}\".\n\n", content), markup)


@router.callback_query(SubjectCb.filter(F.action.in_({"open", "back", "list"})))
async def on_open(callback: CallbackQuery, callback_data: SubjectCb,
                  subject_repo: SubjectRepo) -> None:
    assert isinstance(callback.message, Message)
    user_id = callback.from_user.id
    if callback_data.action == "list":
        await edit(callback.message, *await subjects_list(subject_repo, user_id))
        await callback.answer()
        return

    card = await subject_card(subject_repo, user_id, callback_data.id)
    if card is None:
        await callback.answer(GONE, show_alert=True)
        return
    if callback_data.action == "back":
        await edit(callback.message, *card)
    else:
        await answer(callback.message, *card)
    await callback.answer()


@router.callback_query(SubjectCb.filter(F.action == "classes"))
async def on_classes(callback: CallbackQuery, callback_data: SubjectCb, user_repo: UserRepo,
                     subject_repo: SubjectRepo, event_repo: EventRepo) -> None:
    assert isinstance(callback.message, Message)
    user_id = callback.from_user.id
    subject = await subject_repo.get_subject(user_id, callback_data.id)
    if subject is None:
        await callback.answer(GONE, show_alert=True)
        return
    events = await event_repo.select_of_subject(user_id, subject.id)

    start = callback_data.start
    if start < 0:
        now = await user_now(user_repo, user_id)
        first_ahead = next((i for i, e in enumerate(events) if now and e.end_dt > now), len(events))
        start = max(min(first_ahead, len(events) - CLASSES_PAGE), 0)

    content = Text(Bold(subject.title), "\n\n", "Pick a class to add a note for it alone.")
    await edit(callback.message, content, classes_keyboard(subject, events, start))
    await callback.answer()


@router.callback_query(SubjectCb.filter(F.action.in_({"mutes", "mute"})))
async def on_mutes(callback: CallbackQuery, callback_data: SubjectCb,
                   subject_repo: SubjectRepo) -> None:
    assert isinstance(callback.message, Message)
    user_id = callback.from_user.id
    subject = await subject_repo.get_subject(user_id, callback_data.id)
    if subject is None:
        await callback.answer(GONE, show_alert=True)
        return

    if callback_data.action == "mute":
        if callback_data.type:
            event_type = EventType[callback_data.type]
            await subject_repo.set_series_muted(user_id, subject.id, event_type,
                                                event_type not in subject.muted_types)
        else:
            await subject_repo.set_muted(user_id, subject.id, not subject.muted)
        log.info("user %s: toggled mute %s on subject %s", user_id, callback_data.type or "all",
                 subject.id)
        subject = await subject_repo.get_subject(user_id, subject.id)
        assert subject

    await edit(callback.message, format_mutes(subject), mutes_keyboard(subject))
    await callback.answer()


@router.callback_query(SubjectCb.filter(F.action == "alias"))
async def on_alias(callback: CallbackQuery, callback_data: SubjectCb, state: FSMContext,
                   subject_repo: SubjectRepo) -> None:
    subject = await subject_repo.get_subject(callback.from_user.id, callback_data.id)
    if subject is None:
        await callback.answer(GONE, show_alert=True)
        return
    target = Target(kind="alias", origin="subject", origin_id=subject.id, subject_id=subject.id)
    await start_prompt(callback, state, target, format_alias_prompt(subject),
                       has_current=bool(subject.alias))


@router.callback_query(SubjectCb.filter(F.action == "note"))
async def on_note(callback: CallbackQuery, callback_data: SubjectCb, state: FSMContext,
                  subject_repo: SubjectRepo) -> None:
    subject = await subject_repo.get_subject(callback.from_user.id, callback_data.id)
    if subject is None:
        await callback.answer(GONE, show_alert=True)
        return

    origin, origin_id = ("event", callback_data.event) if callback_data.event else ("subject", subject.id)
    if callback_data.type:
        event_type = EventType[callback_data.type]
        scope = f"all {TYPE_PLURAL[event_type].lower()} ({event_type.value}) of {subject.title}"
        current = subject.series_notes.get(event_type)
        target = Target(kind="series", origin=origin, origin_id=origin_id,
                        subject_id=subject.id, type=event_type.name)
    else:
        scope = f"{subject.title}, every class of it"
        current = subject.note
        target = Target(kind="subject", origin=origin, origin_id=origin_id, subject_id=subject.id)
    await start_prompt(callback, state, target, format_note_prompt(scope, current),
                       has_current=bool(current))
