import logging
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message
from aiogram.utils.formatting import Text

from bot.keyboards import without_links

log = logging.getLogger(__name__)

Markup = InlineKeyboardMarkup | None


async def _with_link_fallback(call: Callable[[Markup], Awaitable[object]], markup: Markup) -> None:
    try:
        await call(markup)
    except TelegramBadRequest as e:
        if "BUTTON_URL_INVALID" not in str(e):
            raise
        log.warning("telegram rejected a link button, sending without links: %s", e)
        await call(without_links(markup))


async def answer(message: Message, content: Text, markup: Markup = None) -> None:
    await _with_link_fallback(
        lambda m: message.answer(**content.as_kwargs(), reply_markup=m), markup)


async def send(bot: Bot, chat_id: int, content: Text, markup: Markup = None) -> None:
    await _with_link_fallback(
        lambda m: bot.send_message(chat_id, **content.as_kwargs(), reply_markup=m), markup)


async def edit(message: Message, content: Text, markup: Markup = None) -> None:
    async def call(m: Markup) -> None:
        try:
            await message.edit_text(**content.as_kwargs(), reply_markup=m)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    await _with_link_fallback(call, markup)
