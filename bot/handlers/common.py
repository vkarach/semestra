from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.commands import help_content

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Semestra on air. /help to see commands.")


@router.message(Command("help"))
async def cmd_help(message: Message, is_admin: bool) -> None:
    section = help_content(admin=is_admin)
    await message.answer(**section.as_kwargs())


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    await message.answer("Testik :)")
