from aiogram import BaseMiddleware


class EnsureUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data["event_from_user"]
        await data["user_repo"].ensure_user(user.id)
        return await handler(event, data)
