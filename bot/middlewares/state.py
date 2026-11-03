import logging

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

log = logging.getLogger(__name__)


class ResetStateMiddleware(BaseMiddleware):
    """Drop a half-finished input as soon as the user does something else."""

    _KEEP_COMMANDS = ("/cancel",)

    def __init__(self, callback_owners: dict[str, str]):
        self._callback_owners = callback_owners

    def _abandons(self, event, current: str) -> bool:
        if isinstance(event, Message):
            text = event.text or ""
            return text.startswith("/") and not text.startswith(self._KEEP_COMMANDS)
        if isinstance(event, CallbackQuery):
            owner = self._callback_owners.get(current.split(":", 1)[0])
            return owner is None or not (event.data or "").startswith(owner)
        return False

    async def __call__(self, handler, event, data):
        state: FSMContext | None = data.get("state")
        if state is not None:
            current = await state.get_state()
            if current is not None and self._abandons(event, current):
                log.info("dropping pending %s", current)
                await state.clear()
        return await handler(event, data)
