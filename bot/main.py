import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from bot.handlers import router
from db import connect, EventRepo
from logging_config import setup_logging

log = logging.getLogger(__name__)


async def main():
    setup_logging()
    load_dotenv()

    conn = await connect()
    event_repo = EventRepo(conn)

    bot = Bot(token=os.environ["BOT_TOKEN"])
    dp = Dispatcher()
    dp.include_router(router)

    try:
        await dp.start_polling(bot, event_repo=event_repo)
    finally:
        await conn.close()
        log.info("shut down")


if __name__ == "__main__":
    asyncio.run(main())
