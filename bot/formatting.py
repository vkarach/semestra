from datetime import date, datetime, timedelta
from itertools import groupby

from aiogram.utils.formatting import Bold, Text, as_marked_section

from models import Event

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


def format_event(e: Event, now: datetime, with_status: bool = True) -> Text:
    return Text(
        Bold(f"{e.start_dt:%H:%M}-{e.end_dt:%H:%M}"), " ",
        e.name, f" ({e.type.value})",
        STATUS_MARK[status(e, now)] if with_status else "",
    )


def format_next(e: Event, now: datetime) -> Text:
    delta = e.start_dt - now
    header = "Starting now" if delta < timedelta(minutes=1) else f"Next up in {format_time_until(delta)}"
    return Text(
        Bold(header), "\n\n",
        Bold(e.name), "\n",
        f"{e.type.value} - {e.start_dt:%a %d %b}, {e.start_dt:%H:%M}-{e.end_dt:%H:%M}",
    )


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
