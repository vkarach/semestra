from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.formatting import Text

from bot.formatting import format_card, format_subject, format_subjects
from bot.handlers.shared import user_now
from bot.keyboards import card_keyboard, subject_keyboard, subjects_keyboard
from db import EventRepo, SubjectRepo, UserRepo

Card = tuple[Text, InlineKeyboardMarkup]


async def event_card(event_repo: EventRepo, user_repo: UserRepo,
                     user_id: int, event_id: int) -> Card | None:
    event = await event_repo.get_event(user_id, event_id)
    now = await user_now(user_repo, user_id)
    if event is None or now is None:
        return None
    return format_card(event, now), card_keyboard(event)


async def subject_card(subject_repo: SubjectRepo, user_id: int, subject_id: int) -> Card | None:
    subject = await subject_repo.get_subject(user_id, subject_id)
    if subject is None:
        return None
    return format_subject(subject), subject_keyboard(subject)


async def subjects_list(subject_repo: SubjectRepo, user_id: int) -> Card:
    subjects = await subject_repo.list_subjects(user_id)
    return format_subjects(subjects), subjects_keyboard(subjects)
