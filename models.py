from datetime import datetime
from enum import Enum


class EventType(Enum):
    CVICENIE = "Cvičenie"
    PREDNASKA = "Prednáška"


class Event:
    def __init__(self, name: str, event_type: EventType, start: datetime, end: datetime,
                 id: int | None = None, notified_at: datetime | None = None):
        self.id = id
        self.name: str = name
        self.type: EventType = event_type
        self.day = start.strftime("%A")
        self.start_dt: datetime = start
        self.end_dt: datetime = end
        self.notified_at = notified_at


    def __str__(self):
        return f"{self.name} ({self.type.value}): {self.day} {self.start_dt.strftime('%H:%M')}-{self.end_dt.strftime('%H:%M')}"


    def __repr__(self):
        return self.__str__()
