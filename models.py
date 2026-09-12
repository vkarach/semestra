from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EventType(Enum):
    CVICENIE = "CV"
    PREDNASKA = "P"
    SEMINAR = "S"
    UNKNOWN = "UNK"


class Event:
    def __init__(self, name: str, event_type: EventType, start: datetime, end: datetime,
                 id: int | None = None, notified_at: datetime | None = None):
        self.id = id
        self.name: str = name
        self.type: EventType = event_type
        self.start_dt: datetime = start
        self.end_dt: datetime = end
        self.notified_at = notified_at


    def __str__(self):
        return f"{self.name} ({self.type.value}): {self.start_dt:%A %H:%M}-{self.end_dt:%H:%M}"


    def __repr__(self):
        return self.__str__()


@dataclass
class User:
    id: int
    timezone: str
    remind_before: int | None
    start_notice: bool
