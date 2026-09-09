from aiogram import Bot
from aiogram.types import BotCommandScopeAllPrivateChats, BotCommandScopeChat

from bot.commands import menu


async def setup_commands(bot: Bot, admin_ids: list[int]) -> None:
    await bot.set_my_commands(menu(), scope=BotCommandScopeAllPrivateChats())
    for admin_id in admin_ids:
        await bot.set_my_commands(menu(admin=True), scope=BotCommandScopeChat(chat_id=admin_id))
