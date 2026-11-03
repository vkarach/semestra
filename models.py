import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EventType(Enum):
    CVICENIE = "CV"
    PREDNASKA = "P"
    SEMINAR = "S"
    EXAM = "EXAM"
    UNKNOWN = "UNK"


class MuteLevel(Enum):
    SUBJECT = "subject"
    SERIES = "series"
    CLASS = "class"


DEFAULT_REMIND_MINUTES = 15

_ROOM_RE = re.compile(r"\(([^()]+)\)\s*$")


TYPE_SINGULAR = {
    EventType.CVICENIE: "Lab",
    EventType.PREDNASKA: "Lecture",
    EventType.SEMINAR: "Seminar",
    EventType.EXAM: "Exam",
    EventType.UNKNOWN: "Other",
}

TYPE_PLURAL = {
    EventType.CVICENIE: "Labs",
    EventType.PREDNASKA: "Lectures",
    EventType.SEMINAR: "Seminars",
    EventType.EXAM: "Exams",
    EventType.UNKNOWN: "Other",
}


class Event:
    def __init__(self, name: str, event_type: EventType, start: datetime, end: datetime,
                 id: int | None = None, notified_at: datetime | None = None,
                 location: str | None = None, description: str | None = None,
                 note: str | None = None, cancelled: bool = False,
                 subject_id: int | None = None, alias: str | None = None,
                 series_note: str | None = None, subject_note: str | None = None,
                 muted: bool = False, series_muted: bool = False, subject_muted: bool = False):
        self.id = id
        self.name: str = name
        self.type: EventType = event_type
        self.start_dt: datetime = start
        self.end_dt: datetime = end
        self.notified_at = notified_at
        self.location = location
        self.description = description
        self.note = note
        self.cancelled = cancelled
        self.subject_id = subject_id
        self.alias = alias
        self.series_note = series_note
        self.subject_note = subject_note
        self.muted = muted
        self.series_muted = series_muted
        self.subject_muted = subject_muted


    @property
    def title(self) -> str:
        return self.alias or self.name


    @property
    def silenced_by(self) -> MuteLevel | None:
        if self.subject_muted:
            return MuteLevel.SUBJECT
        if self.series_muted:
            return MuteLevel.SERIES
        if self.muted:
            return MuteLevel.CLASS
        return None


    @property
    def room(self) -> str | None:
        if not self.location:
            return None
        m = _ROOM_RE.search(self.location)
        return m.group(1).strip() if m else self.location


    def __str__(self):
        return f"{self.name} ({self.type.value}): {self.start_dt:%A %H:%M}-{self.end_dt:%H:%M}"


    def __repr__(self):
        return self.__str__()


@dataclass
class Subject:
    id: int
    name: str
    alias: str | None
    note: str | None
    series_notes: dict[EventType, str]
    types: list[EventType]
    muted: bool = False
    muted_types: set[EventType] = field(default_factory=set)

    @property
    def title(self) -> str:
        return self.alias or self.name


@dataclass
class User:
    id: int
    timezone: str | None
    remind_before: int | None
    start_notice: bool
    digest_at: str | None = None
    digest_sent_on: str | None = None
