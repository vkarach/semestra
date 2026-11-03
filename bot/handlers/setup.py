import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from aiogram.utils.formatting import Bold, Pre, Text, as_list

import setup_text
from bot.handlers.shared import NO_TIMETABLE
from bot.sending import answer
from db import AliasTaken, SubjectRepo
from models import Subject

log = logging.getLogger(__name__)

router = Router()

INLINE_EXPORT_LIMIT = 3500
MAX_ERRORS = 15


async def _send_export(message: Message, subjects: list[Subject]) -> None:
    text = setup_text.render(subjects)
    hint = "Copy it, fill in what you need and send it back. An empty line after a colon means no note."
    if len(text) > INLINE_EXPORT_LIMIT:
        await message.answer_document(BufferedInputFile(text.encode(), "setup.txt"), caption=hint)
        return
    await answer(message, Text(Bold("Your setup"), "\n", hint, "\n\n", Pre(text)))


@router.message(Command("setup"))
async def cmd_setup(message: Message, subject_repo: SubjectRepo) -> None:
    assert message.from_user and message.text
    user_id = message.from_user.id
    subjects = await subject_repo.list_subjects(user_id)
    if not subjects:
        await message.answer(NO_TIMETABLE)
        return

    # cut only the command token so line numbers match what the user sent
    body = message.text[len(message.text.split(maxsplit=1)[0]):]
    if not body.strip():
        await _send_export(message, subjects)
        return

    blocks, errors = setup_text.parse(body)
    edits, changes, resolve_errors = setup_text.resolve(blocks, subjects)
    errors = sorted(errors + resolve_errors, key=lambda e: e.line)
    if errors:
        rows = [Text(Bold(f"line {e.line}"), f": {e.message}") for e in errors[:MAX_ERRORS]]
        if len(errors) > MAX_ERRORS:
            rows.append(Text(f"and {len(errors) - MAX_ERRORS} more"))
        await answer(message, Text("Nothing was saved. Fix these and send it again:\n\n",
                                   as_list(*rows)))
        return
    if not edits:
        await message.answer("Everything is already set like this.")
        return

    try:
        await subject_repo.apply_edits(user_id, edits)
    except AliasTaken:
        await message.answer("Nothing was saved: a shortcut is taken by a subject from an older "
                             "timetable. Pick a different one.")
        return
    log.info("user %s: setup changed %d subjects", user_id, len(edits))
    titles = {s.id: s.name for s in subjects}
    rows = [Text(Bold(titles[sid]), ": ", ", ".join(parts)) for sid, parts in changes.items()]
    await answer(message, Text("Saved.\n\n", as_list(*rows), "\n\n", "Check with /subjects"))
