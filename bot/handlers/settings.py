import re

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.formatting import format_settings
from db import UserRepo

router = Router()

_TIME_RE = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")


@router.message(Command("remind"))
async def cmd_remind(message: Message, command: CommandObject, user_repo: UserRepo) -> None:
    assert message.from_user
    arg = (command.args or "").strip().lower()
    if arg == "off":
        await user_repo.set_remind_before(message.from_user.id, 0)
        await message.answer("Reminders before events are off")
        return
    if not arg.isdigit() or not 1 <= int(arg) <= 1440:
        await message.answer("Usage: /remind <minutes>, 1-1440, or /remind off")
        return
    await user_repo.set_remind_before(message.from_user.id, int(arg))
    await message.answer(f"Reminders will arrive {arg} min before each event")


@router.message(Command("start_notice"))
async def cmd_start_notice(message: Message, user_repo: UserRepo) -> None:
    assert message.from_user
    enabled = await user_repo.toggle_start_notice(message.from_user.id)
    await message.answer(f"Start notice is turned {'on' if enabled else 'off'}")


@router.message(Command("digest"))
async def cmd_digest(message: Message, command: CommandObject, user_repo: UserRepo) -> None:
    assert message.from_user
    arg = (command.args or "").strip().lower()
    if arg == "off":
        await user_repo.set_digest_at(message.from_user.id, None)
        await message.answer("Morning digest is off")
        return
    m = _TIME_RE.fullmatch(arg)
    if not m:
        await message.answer("Usage: /digest HH:MM to get the day's schedule at that time, "
                             "or /digest off")
        return
    digest_at = f"{int(m.group(1)):02d}:{m.group(2)}"
    await user_repo.set_digest_at(message.from_user.id, digest_at)
    await message.answer(f"Every day with classes, the schedule arrives at {digest_at}")


@router.message(Command("settings"))
async def cmd_settings(message: Message, user_repo: UserRepo) -> None:
    assert message.from_user
    user = await user_repo.get_user(message.from_user.id)
    assert user
    await message.answer(**format_settings(user).as_kwargs())
