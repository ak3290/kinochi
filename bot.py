from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import ADMINS, BOT_TOKEN
from database import db
from handlers import get_routers
from middlewares import SubscriptionMiddleware
from utils import EMOJI_KEY, TEMPLATE_KEY, set_bot_username, set_emoji_ids, set_template

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await db.connect()
    set_template(await db.get_setting(TEMPLATE_KEY))
    set_emoji_ids(await db.get_setting(EMOJI_KEY))

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Majburiy obuna — barcha handlerlardan oldin ishlaydi
    dp.message.outer_middleware(SubscriptionMiddleware())
    dp.callback_query.outer_middleware(SubscriptionMiddleware())

    dp.include_routers(*get_routers())

    me = await bot.get_me()
    set_bot_username(me.username)
    logger.info("Bot ishga tushdi: @%s | adminlar: %s", me.username, ADMINS or "yo'q")
    if not ADMINS:
        logger.warning("ADMINS bo'sh! .env faylida ADMINS ni to'ldiring.")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
