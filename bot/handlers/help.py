from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.formatting import Text, Bold, as_list, Code, as_section

router = Router()


@router.message(Command("ics_help"))
async def cmd_ics_help(message: Message) -> None:
    about_ics = as_list(
        Bold("ICS file format"),
        Text(
            Code(".ics"),
            " (iCalendar) is the standard format for calendar events. ",
            "It can be imported into almost any calendar app, such as Google Calendar, Apple Calendar or Outlook.",
        ),
        as_section(
            Bold("Export from MAIS"),
            as_list(
                Text("Open ", Bold("Rozvrh"), " (timetable) → ", Bold("iCal export")),
                "Then use /add_events to upload it.",
            ),
        ),
        sep="\n\n",
    )
    await message.answer(**about_ics.as_kwargs())
