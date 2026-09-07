import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from bot.handlers import router
from db import connect, EventRepo


async def main():
    logging.basicConfig(level=logging.INFO)
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


if __name__ == "__main__":
    asyncio.run(main())
