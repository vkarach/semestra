from dataclasses import dataclass
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


def parse_ics(raw: bytes) -> ParsedTimetable:
    cal = Calendar.from_ical(raw)

    tz_str = _extract_timezone(cal)

    events = []
    skipped = 0
    for component in cal.walk("VEVENT"):
        summary = str(component.get("SUMMARY"))

        event_name = summary.split('(')[0].strip()
        event_type = EventType.CVICENIE if "Cvičenie" in summary else EventType.PREDNASKA
        start_dt = component.get("DTSTART").dt

        try:
            end_dt = component.get("DTEND").dt
        except AttributeError:
            # end_dt = start_dt + component.get("DURATION").dt
            skipped += 1
            continue

        event = Event(event_name, event_type, start_dt, end_dt)
        events.append(event)

    log.info("parsed %d events, skipped %d without DTEND", len(events), skipped)
    return ParsedTimetable(tz_str, events)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str, help="path to file")
    args = parser.parse_args()

    print(parse_ics(args.input))
