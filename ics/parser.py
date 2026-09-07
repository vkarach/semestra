from zoneinfo import ZoneInfo
import argparse
import logging

from icalendar import Calendar
from models import Event, EventType

log = logging.getLogger(__name__)


def parse_ics(raw: bytes) -> list[Event]:
    cal = Calendar.from_ical(raw)

    try:
        tzid = cal["X-WR-TIMEZONE"].to_ical().decode() # todo: only X-WR-TIMEZONE, add VTIMEZONE fallback
        tz = ZoneInfo(tzid)
    except Exception as e:
        log.warning("no usable X-WR-TIMEZONE: %s", e)

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
    return events



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str, help="path to file")
    args = parser.parse_args()

    events = parse_ics(args.input)
    print(events)
