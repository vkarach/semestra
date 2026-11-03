from datetime import date, timedelta

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import notes
from bot.formatting import event_button_text, merged_note, subject_button_text
from models import TYPE_PLURAL, Event, Subject

MAX_LINK_BUTTONS = 8
CLASSES_PAGE = 8


class DayCb(CallbackData, prefix="day"):
    day: str


class EventCb(CallbackData, prefix="ev"):
    action: str
    id: int


class SubjectCb(CallbackData, prefix="subj"):
    action: str
    id: int
    type: str = ""
    start: int = -1
    event: int = 0


class PromptCb(CallbackData, prefix="prompt"):
    action: str


def _day_button(text: str, day: date) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=DayCb(day=day.isoformat()).pack())


def _day_name(day: date, today: date) -> str:
    return "Today" if day == today else f"{day:%a %d}"


def _event_button(e: Event, with_day: bool) -> InlineKeyboardButton:
    assert e.id is not None
    return InlineKeyboardButton(text=event_button_text(e, with_day=with_day),
                                callback_data=EventCb(action="open", id=e.id).pack())


def link_rows(note: notes.ParsedNote) -> list[list[InlineKeyboardButton]]:
    buttons = [InlineKeyboardButton(text=key[:32], url=url)
               for key, url in note.links()[:MAX_LINK_BUTTONS]]
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def links_keyboard(note: notes.ParsedNote) -> InlineKeyboardMarkup | None:
    rows = link_rows(note)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def without_links(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    if markup is None:
        return None
    rows = [[b for b in row if b.url is None] for row in markup.inline_keyboard]
    rows = [row for row in rows if row]
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def day_keyboard(day: date, today: date, events: list[Event]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for e in events:
        builder.row(_event_button(e, with_day=False))
    prev_day, next_day = day - timedelta(days=1), day + timedelta(days=1)
    nav = [_day_button(f"< {_day_name(prev_day, today)}", prev_day)]
    if today not in (prev_day, day, next_day):
        nav.append(_day_button("Today", today))
    nav.append(_day_button(f"{_day_name(next_day, today)} >", next_day))
    builder.row(*nav)
    return builder.as_markup()


def event_list_keyboard(events: list[Event]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for e in events:
        builder.row(_event_button(e, with_day=True))
    return builder.as_markup()


def card_keyboard(e: Event) -> InlineKeyboardMarkup:
    assert e.id is not None and e.subject_id is not None
    series = SubjectCb(action="note", id=e.subject_id, type=e.type.name, event=e.id)
    rows = [
        [
            InlineKeyboardButton(text="Note: this class",
                                 callback_data=EventCb(action="note", id=e.id).pack()),
            InlineKeyboardButton(text=f"Note: all {TYPE_PLURAL[e.type].lower()}",
                                 callback_data=series.pack()),
        ],
        [
            InlineKeyboardButton(text=f"Subject: {e.title}"[:40],
                                 callback_data=SubjectCb(action="open", id=e.subject_id).pack()),
            InlineKeyboardButton(text="Restore class" if e.cancelled else "Mark cancelled",
                                 callback_data=EventCb(action="cancel", id=e.id).pack()),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=link_rows(merged_note(e)) + rows)


def subjects_keyboard(subjects: list[Subject]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in subjects:
        builder.row(InlineKeyboardButton(text=subject_button_text(s),
                                         callback_data=SubjectCb(action="open", id=s.id).pack()))
    return builder.as_markup()


def subject_keyboard(s: Subject) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Change shortcut" if s.alias else "Set shortcut",
                   callback_data=SubjectCb(action="alias", id=s.id))
    builder.button(text="Note: whole subject", callback_data=SubjectCb(action="note", id=s.id))
    for t in s.types:
        builder.button(text=f"Note: {TYPE_PLURAL[t].lower()}",
                       callback_data=SubjectCb(action="note", id=s.id, type=t.name))
    builder.button(text="Pick a class", callback_data=SubjectCb(action="classes", id=s.id))
    builder.button(text="< All subjects", callback_data=SubjectCb(action="list", id=s.id))
    builder.adjust(2)
    for row in link_rows(notes.parse(s.note)):
        builder.row(*row)
    return builder.as_markup()


def classes_keyboard(s: Subject, events: list[Event], start: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for e in events[start:start + CLASSES_PAGE]:
        builder.row(_event_button(e, with_day=True))
    nav = []
    if start > 0:
        earlier = SubjectCb(action="classes", id=s.id, start=max(start - CLASSES_PAGE, 0))
        nav.append(InlineKeyboardButton(text="< Earlier", callback_data=earlier.pack()))
    if start + CLASSES_PAGE < len(events):
        later = SubjectCb(action="classes", id=s.id, start=start + CLASSES_PAGE)
        nav.append(InlineKeyboardButton(text="Later >", callback_data=later.pack()))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text=f"< {s.title}"[:40],
                                     callback_data=SubjectCb(action="back", id=s.id).pack()))
    return builder.as_markup()


def prompt_keyboard(has_current: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_current:
        builder.button(text="Clear", callback_data=PromptCb(action="clear"))
    builder.button(text="Back", callback_data=PromptCb(action="back"))
    return builder.as_markup()
