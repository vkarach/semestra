import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from bot.handlers import router
from bot.middlewares import EnsureUserMiddleware, AdminMiddleware, PermissionMiddleware
from bot.setup import setup_commands
from bot.notifier import setup_notifier

from db import connect, EventRepo
from db.user import UserRepo

from logging_config import setup_logging

log = logging.getLogger(__name__)

ADMIN_IDS = []


async def on_startup(bot: Bot) -> None:
    await setup_commands(bot, ADMIN_IDS)


async def main():
    setup_logging()
    load_dotenv()

    conn = await connect()
    event_repo = EventRepo(conn)
    user_repo = UserRepo(conn)

    bot = Bot(token=os.environ["BOT_TOKEN"])
    dp = Dispatcher()
    dp.include_router(router)

    dp.update.outer_middleware(EnsureUserMiddleware())
    dp.update.outer_middleware(AdminMiddleware(ADMIN_IDS))

    dp.message.middleware(PermissionMiddleware())

    dp.startup.register(on_startup)

    scheduler = setup_notifier(bot, event_repo=event_repo, user_repo=user_repo)
    scheduler.start()

    try:
        await dp.start_polling(bot, event_repo=event_repo, user_repo=user_repo)
    finally:
        await conn.close()
        scheduler.shutdown(wait=False)
        log.info("shut down")


if __name__ == "__main__":
    asyncio.run(main())
