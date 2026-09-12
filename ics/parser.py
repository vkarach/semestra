from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import argparse
import logging

from icalendar import Calendar
from models import Event, EventType

log = logging.getLogger(__name__)

@dataclass(slots=True)
class ParsedTimetable:
    timezone: str | None
    events: list[Event]


def _extract_timezone(cal: Calendar) -> str | None:
    candidates = []
    if "X-WR-TIMEZONE" in cal:
        candidates.append(cal["X-WR-TIMEZONE"].to_ical().decode())
    for component in cal.walk("VEVENT"):
        tzid = component.get("DTSTART").params.get("TZID")
        if tzid:
            candidates.append(str(tzid))
            break

    for tzid in candidates:
        try:
            ZoneInfo(tzid)
            return tzid
        except (ZoneInfoNotFoundError, ValueError):
            log.warning("unusable timezone %r", tzid)
    return None


def _weekly_occurrences(start: datetime, rrule) -> list[datetime]:
    if not rrule:
        return [start]
    if rrule.get("FREQ", ["WEEKLY"])[0] != "WEEKLY":
        log.warning("unsupported RRULE FREQ %r, keeping single occurrence", rrule.get("FREQ"))
        return [start]

    until = rrule.get("UNTIL", [None])[0]
    if isinstance(until, datetime):
        until = until.replace(tzinfo=None)
    if until is None:
        log.warning("weekly RRULE without UNTIL, keeping single occurrence")
        return [start]

    step = timedelta(weeks=int(rrule.get("INTERVAL", [1])[0]))
    out, cur = [], start
    while cur <= until:
        out.append(cur)
        cur += step
    return out


def parse_ics(raw: bytes) -> ParsedTimetable:
    cal = Calendar.from_ical(raw)

    tz_str = _extract_timezone(cal)

    events = []
    skipped = 0
    for component in cal.walk("VEVENT"):
        summary = str(component.get("SUMMARY"))

        event_name = summary.split('(')[0].strip()
        if "Cvičenie" in summary:
            event_type = EventType.CVICENIE
        elif "Prednáška" in summary:
            event_type = EventType.PREDNASKA
        elif "Seminár" in summary:
            event_type = EventType.SEMINAR
        else:
            event_type = EventType.UNKNOWN

        start_dt = component.get("DTSTART").dt

        try:
            end_dt = component.get("DTEND").dt
        except AttributeError:
            skipped += 1
            continue

        duration = end_dt - start_dt
        for occ_start in _weekly_occurrences(start_dt, component.get("RRULE")):
            events.append(Event(event_name, event_type, occ_start, occ_start + duration))

    log.info("parsed %d events, skipped %d without DTEND", len(events), skipped)
    return ParsedTimetable(tz_str, events)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str, help="path to file")
    args = parser.parse_args()

    print(parse_ics(args.input))
