from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Semestra on air. /add_events to add events.")
