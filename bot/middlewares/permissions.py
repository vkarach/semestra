from aiogram import BaseMiddleware
from aiogram.filters import CommandObject

from bot.commands import BY_NAME, is_allowed


class PermissionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        command: CommandObject | None = data.get("command")
        if command is None:
            return await handler(event, data)

        spec = BY_NAME.get(command.command)
        if spec is None:
            return await handler(event, data)

        if not is_allowed(spec, admin=data.get("is_admin", False)):
            await event.answer("Not allowed.")
            return None

        return await handler(event, data)
