from datetime import date, datetime, timedelta
from itertools import groupby

from aiogram.utils.formatting import (
    Bold, Code, Italic, Pre, Strikethrough, Text, Url, as_list, as_marked_section,
)

import notes
from models import (
    DEFAULT_REMIND_MINUTES, TYPE_PLURAL, TYPE_SINGULAR, Event, EventType, MuteLevel, Subject,
    User,
)

STATUS_MARK = {"done": " ✓", "now": " ▶", "upcoming": ""}

NO_EVENTS_AT_ALL = Text("No events yet, send your timetable: /add_events")


def status(e: Event, now: datetime) -> str:
    if e.end_dt <= now:
        return "done"
    if e.start_dt <= now:
        return "now"
    return "upcoming"


def format_time_until(delta: timedelta) -> str:
    total_minutes = -(-int(delta.total_seconds()) // 60)
    days, rem = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


def day_label(day: date, today: date) -> str:
    if day == today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    if day == today - timedelta(days=1):
        return "yesterday"
    return f"on {day:%a %d %b}"


def series_label(event_type: EventType) -> str:
    return f"{TYPE_PLURAL[event_type]} ({event_type.value})"


def format_note(note: notes.ParsedNote, indent: str = "") -> list[Text]:
    rows = [
        Text(indent, Bold(key), ": ", Url(value) if notes.is_url(value) else value)
        for key, value in note.items()
    ]
    rows += [Text(indent, Url(line) if notes.is_url(line) else Italic(line)) for line in note.lines]
    return rows


def mute_reason(e: Event) -> str:
    match e.silenced_by:
        case MuteLevel.SUBJECT:
            return f"Reminders off for all of {e.title}"
        case MuteLevel.SERIES:
            return f"Reminders off for all {TYPE_PLURAL[e.type].lower()} of {e.title}"
        case MuteLevel.CLASS:
            return "Reminders off for this class"
    return "Reminders on"


def merged_note(e: Event) -> notes.ParsedNote:
    return notes.merge(e.subject_note, e.series_note, e.note)


def format_event(e: Event, now: datetime, with_status: bool = True) -> Text:
    line = Text(
        Bold(f"{e.start_dt:%H:%M}-{e.end_dt:%H:%M}"), " ",
        e.title, f" ({e.type.value})",
        f", {e.room}" if e.room else "",
    )
    if e.cancelled:
        line = Text(Strikethrough(line), " cancelled")
    elif with_status:
        line = Text(line, STATUS_MARK[status(e, now)])
    return as_list(line, *format_note(notes.parse(e.note), indent="    "))


def format_details(e: Event) -> Text:
    lines: list[Text | str] = [Bold(e.title, " - ", TYPE_SINGULAR[e.type])]
    if e.alias:
        lines.append(e.name)
    lines.append(f"{e.start_dt:%a %d %b}, {e.start_dt:%H:%M}-{e.end_dt:%H:%M}")
    if e.location:
        lines.append(Text("Where: ", e.location))
    if e.description:
        lines.append(Text("Info: ", e.description))
    if e.cancelled:
        lines.append(Bold("Cancelled, no reminders for it"))
    elif e.silenced_by is not None:
        lines.append(Bold(mute_reason(e)))
    note = merged_note(e)
    if note:
        lines += ["", Bold("Notes"), *format_note(note)]
    return as_list(*lines)


def format_card(e: Event, now: datetime) -> Text:
    state = status(e, now)
    if state == "done":
        header = "Finished"
    elif state == "now":
        header = "In progress"
    else:
        delta = e.start_dt - now
        header = "Starting now" if delta < timedelta(minutes=1) else f"In {format_time_until(delta)}"
    return Text(Bold(header), "\n\n", format_details(e))


def format_next(e: Event, now: datetime) -> Text:
    delta = e.start_dt - now
    header = "Starting now" if delta < timedelta(minutes=1) else f"Next up in {format_time_until(delta)}"
    return Text(Bold(header), "\n\n", format_details(e))


def _alert(e: Event, headline: str) -> Text:
    return as_list(
        Text(Bold(e.title), f" ({e.type.value}) {headline}"),
        *([Text("Where: ", e.room)] if e.room else []),
        *format_note(merged_note(e)),
    )


def format_reminder(e: Event, minutes: int) -> Text:
    return _alert(e, f"in {minutes} min, starts {e.start_dt:%H:%M}")


def format_start_notice(e: Event) -> Text:
    return _alert(e, "now!")


def format_closest(e: Event, now: datetime, label: str) -> Text:
    return Text(Bold(f"No events {label}"), "\n\n", format_next(e, now))


def format_nothing_ahead(label: str | None = None) -> Text:
    if label is None:
        return Text("Nothing ahead, your timetable ends here")
    return Text(f"No events {label}, and nothing ahead either")


def format_section(day: date, day_events: list[Event], now, with_status: bool = True) -> Text:
    return as_marked_section(
        Bold(f"{day:%A}, {day:%d %b}"),
        *[format_event(e, now, with_status) for e in day_events],
        marker="",
    )


def format_schedule(events: list[Event], now, with_status: bool = True) -> list[Text]:
    return [
        format_section(day, list(day_events), now, with_status)
        for day, day_events in groupby(events, key=lambda e: e.start_dt.date())
    ]


def format_digest(day: date, events: list[Event], now: datetime) -> Text:
    return Text(Bold("Today's schedule"), "\n\n", format_section(day, events, now))


def format_exams(exams: list[Event], now: datetime) -> Text:
    if not exams:
        return Text("No upcoming exams in your timetable")
    rows = [
        as_list(
            Text(
                Bold(f"{e.start_dt:%a %d %b}, {e.start_dt:%H:%M}-{e.end_dt:%H:%M}"),
                f" (in {format_time_until(e.start_dt - now)})" if e.start_dt > now else " (now)",
            ),
            Text(e.title, f", {e.room}" if e.room else ""),
            *format_note(notes.parse(e.note)),
        )
        for e in exams
    ]
    return as_list(Bold("Upcoming exams"), *rows, sep="\n\n")


def format_subjects(subjects: list[Subject]) -> Text:
    if not subjects:
        return NO_EVENTS_AT_ALL
    return Text(
        Bold("Subjects"), "\n\n",
        "Pick one to set its shortcut or notes. ",
        Code("/subjects ux"), " opens one by name or shortcut.",
    )


def _note_section(title: str, note: str | None) -> Text:
    parsed = notes.parse(note)
    body = format_note(parsed) if parsed else [Italic("no notes")]
    return as_list(Bold(title), *body)


def format_subject(s: Subject) -> Text:
    head = [Bold(s.title)]
    if s.alias:
        head.append(s.name)
    head.append(Text("Shortcut: ", s.alias or "none"))
    head.append(Text("Reminders: ", _mute_summary(s)))
    sections = [_note_section("Whole subject", s.note)]
    sections += [_note_section(series_label(t), s.series_notes.get(t)) for t in s.types]
    return as_list(as_list(*head), *sections, sep="\n\n")


def _mute_summary(s: Subject) -> str:
    if s.muted:
        return "off for the whole subject"
    muted = [series_label(t).lower() for t in s.types if t in s.muted_types]
    if not muted:
        return "on"
    if len(muted) == len(s.types):
        return "off for every type"
    return "off for " + ", ".join(muted)


def format_mutes(s: Subject) -> Text:
    return Text(
        Bold("Reminders for ", s.title), "\n\n",
        "Tap to switch. Muted classes still show in the schedule and the digest, ",
        "they only get no reminder and no start notice. ",
        "A single class is muted from its own card.\n\n",
        Text("Reminders: ", _mute_summary(s)),
    )


NOTE_FORMAT_HELP = Text(
    "One ", Code("key: value"), " per line, links become buttons. Plain lines stay as text. "
    "JSON like ", Code('{"isi": "https://..."}'), " works too. "
    "What you send replaces the whole note.",
)


def format_note_prompt(scope: str, current: str | None) -> Text:
    parts: list[Text | str] = [Bold("Note for ", scope), "\n\n", NOTE_FORMAT_HELP, "\n\n"]
    if current:
        parts += ["Current, tap to copy:\n", Pre(current), "\n"]
    parts.append(Text(f"Send the text, up to {notes.MAX_LEN} characters, or /cancel."))
    return Text(*parts)


def format_alias_prompt(s: Subject) -> Text:
    return Text(
        Bold("Shortcut for ", s.name), "\n\n",
        "It replaces the full name in schedules, reminders and buttons, and finds the subject in ",
        Code("/subjects"), ". Up to 24 characters, for example ", Code("UX"), ".\n\n",
        Text("Current: ", Code(s.alias), "\n\n") if s.alias else "",
        "Send the shortcut, or /cancel.",
    )


def format_settings(user: User) -> Text:
    if user.remind_before == 0:
        remind = "off"
    else:
        remind = f"{user.remind_before or DEFAULT_REMIND_MINUTES} min before"
    return as_list(
        Bold("Settings"),
        Text("Timezone: ", user.timezone or "not set, send your timetable: /add_events"),
        Text("Reminders: ", remind, "  /remind"),
        Text("Start notice: ", "on" if user.start_notice else "off", "  /start_notice"),
        Text("Morning digest: ", user.digest_at or "off", "  /digest"),
    )


def event_button_text(e: Event, with_day: bool = False) -> str:
    when = f"{e.start_dt:%a %d %b %H:%M}" if with_day else f"{e.start_dt:%H:%M}"
    mark = " (cancelled)" if e.cancelled else (" *" if e.note else "")
    return f"{when} {e.title} ({e.type.value}){mark}"


def subject_button_text(s: Subject) -> str:
    return f"{s.alias} - {s.name}" if s.alias else s.name
