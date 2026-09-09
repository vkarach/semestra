from aiogram import BaseMiddleware


class AdminMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: list[int]) -> None:
        self.admin_ids = admin_ids


    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        data["is_admin"] = user is not None and user.id in self.admin_ids
        return await handler(event, data)
