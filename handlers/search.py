from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import db
from utils import esc, movie_caption

router = Router()
logger = logging.getLogger(__name__)

NOT_FOUND = (
    "😔 <b>Hech narsa topilmadi</b>\n\n"
    "<blockquote>Kod to'g'ri kiritilganini tekshiring yoki kino nomini "
    "boshqacha yozib ko'ring.</blockquote>"
)


async def send_movie(message: Message, movie, count_view: bool = True) -> bool:
    # Ko'rishlar soni caption'da darhol yangilangan holda ko'rinadi
    caption = movie_caption(movie, views=movie["views"] + (1 if count_view else 0))
    try:
        if movie["file_type"] == "document":
            await message.answer_document(movie["file_id"], caption=caption)
        else:
            await message.answer_video(movie["file_id"], caption=caption)
    except TelegramAPIError as error:
        logger.error("Kinoni yuborib bo'lmadi (id=%s): %s", movie["id"], error)
        await message.answer("⚠️ Bu kinoni yuborishda xatolik yuz berdi. Adminga xabar bering.")
        return False
    if count_view:
        await db.increment_views(movie["id"])
    return True


def results_kb(movies) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🎬 {movie['title'][:40] or movie['code']}",
                    callback_data=f"get:{movie['id']}",
                )
            ]
            for movie in movies
        ]
    )


@router.message(F.text & ~F.text.startswith("/"))
async def search(message: Message) -> None:
    query = message.text.strip()
    if not query:
        return

    await db.add_user(
        message.from_user.id, message.from_user.full_name, message.from_user.username
    )

    movie = await db.get_movie_by_code(query)
    if movie:
        await send_movie(message, movie)
        return

    movies = await db.search_movies(query)
    if not movies:
        await message.answer(NOT_FOUND)
        return

    if len(movies) == 1:
        await send_movie(message, movies[0])
        return

    await message.answer(
        f"🔎 «{esc(query)}» bo'yicha {len(movies)} ta natija topildi:",
        reply_markup=results_kb(movies),
    )


@router.callback_query(F.data.startswith("get:"))
async def get_movie(callback: CallbackQuery) -> None:
    movie_id = int(callback.data.split(":")[1])
    movie = await db.get_movie(movie_id)
    if not movie:
        await callback.answer("Bu kino o'chirilgan.", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await send_movie(callback.message, movie)
