from dataclasses import dataclass
from enum import Enum

from aiogram.types import BotCommand
from aiogram.utils.formatting import BotCommand as CommandText
from aiogram.utils.formatting import as_marked_section, Text, Bold, as_list


class Access(Enum):
    EVERYONE = "everyone"
    ADMIN = "admin"


@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    group: str = "General"
    access: Access = Access.EVERYONE
    hidden: bool = False


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("start", "Start the bot"),
    CommandSpec("help", "Show all commands"),
    CommandSpec("cancel", "Cancel the current operation"),

    CommandSpec("today", "Schedule for today", group="Schedule"),
    CommandSpec("tomorrow", "Schedule for tomorrow", group="Schedule"),
    CommandSpec("next", "See next event", group="Schedule"),
    CommandSpec("week", "Schedule for this week", group="Schedule"),
    CommandSpec("schedule", "Upcoming events for the next 7 days", group="Schedule"),
    CommandSpec("exams", "Upcoming exams with countdown", group="Schedule"),
    CommandSpec("subjects", "Shortcuts and notes for your subjects", group="Schedule"),
    CommandSpec("add_events", "Upload an .ics timetable", group="Schedule"),

    CommandSpec("settings", "Show current settings", group="Settings"),
    CommandSpec("remind", "Reminder lead time in minutes, or off", group="Settings"),
    CommandSpec("start_notice", "Toggle notification when an event starts", group="Settings"),
    CommandSpec("digest", "Daily schedule at a set time, HH:MM or off", group="Settings"),

    CommandSpec("ics_help", "Information about ics, where get it", group="Help"),

    CommandSpec("admin_info", "Usage statistics", group="Admin", access=Access.ADMIN),
)


BY_NAME: dict[str, CommandSpec] = {c.name: c for c in COMMANDS}


def is_allowed(spec: CommandSpec, *, admin: bool) -> bool:
    return spec.access is Access.EVERYONE or admin


def menu(*, admin: bool = False) -> list[BotCommand]:
    return [
        BotCommand(command=c.name, description=c.description)
        for c in COMMANDS
        if not c.hidden and is_allowed(c, admin=admin)
    ]


def help_content(*, admin: bool = False) -> Text:
    sections = []
    for group in dict.fromkeys(c.group for c in COMMANDS):
        rows = [
            Text(CommandText(f"/{c.name}"), " : ", c.description)
            for c in COMMANDS
            if c.group == group and not c.hidden and is_allowed(c, admin=admin)
        ]
        if not rows:
            continue
        sections.append(as_marked_section(Bold(group), *rows, marker="• "))

    if not sections:
        return Text("No commands available.")
    return as_list(*sections, sep="\n\n")
