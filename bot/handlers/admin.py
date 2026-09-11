from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db.events import EventRepo
from db.user import UserRepo


router = Router()


@router.message(Command("admin_info"))
async def cmd_admin_info(message: Message, user_repo: UserRepo, event_repo: EventRepo) -> None:
    total_users = await user_repo.count_users()
    active_users = await user_repo.count_users_with_timezone()
    total_events = await event_repo.count_events()
    await message.answer(
        f"Users: {total_users} ({active_users} with timezone set)\n"
        f"Events stored: {total_events}"
    )
