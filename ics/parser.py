import argparse

from icalendar import Calendar
from models import Event, EventType


def parse_ics(input_file):
    with open(input_file, "rb") as f:
        cal = Calendar.from_ical(f.read())

    events = []
    for component in cal.walk("VEVENT"):
        summary = str(component.get("SUMMARY"))

        event_name = summary.split('(')[0].strip()
        event_type = EventType.CVICENIE if "Cvičenie" in summary else EventType.PREDNASKA
        start_dt = component.get("DTSTART").dt

        try:
            end_dt = component.get("DTEND").dt
        except AttributeError:
            # end_dt = start_dt + component.get("DURATION").dt
            continue

        event = Event(event_name, event_type, start_dt, end_dt)
        events.append(event)

    return events



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str, help="path to file")
    args = parser.parse_args()

    events = parse_ics(args.input)
    print(events)
