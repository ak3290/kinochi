from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import is_admin
from keyboards import subscribe_kb
from utils import unsubscribed_channels

TEXT = (
    "👋 Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling.\n\n"
    "Obuna bo'lgach — <b>✅ Tekshirish</b> tugmasini bosing."
)


class SubscriptionMiddleware(BaseMiddleware):
    """Majburiy obuna tekshiruvi. Adminlar va tekshirish tugmasi chetlab o'tiladi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        bot: Bot = data["bot"]

        if user is None or is_admin(user.id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "check_subs":
            return await handler(event, data)

        channels = await unsubscribed_channels(bot, user.id)
        if not channels:
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(TEXT, reply_markup=subscribe_kb(channels))
        elif isinstance(event, CallbackQuery):
            await event.answer("Avval kanallarga obuna bo'ling.", show_alert=True)
            if event.message:
                await event.message.answer(TEXT, reply_markup=subscribe_kb(channels))
        return None
