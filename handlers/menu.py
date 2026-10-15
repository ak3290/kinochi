"""Foydalanuvchi uchun inline menyu: yangi/top kinolar, janrlar, qidiruv, yordam."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import is_admin
from database import db
from keyboards import PAGE_SIZE, user_menu_kb
from utils import esc

from .start import welcome

router = Router()

HELP = (
    "ℹ️ <b>Yordam</b>\n\n"
    "▫️ Kino <b>kodini</b> yuboring — masalan: <code>101</code>\n"
    "▫️ Yoki kino <b>nomini</b> yozing — masalan: <code>Titanik</code>\n"
    "▫️ Yoki pastdagi tugmalardan foydalaning 👇"
)

HOME_ROW = [InlineKeyboardButton(text="🏠 Menyu", callback_data="u:home")]


async def show(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    """Xabarni joyida yangilaydi (tugmalar bosilganda chat to'lib ketmasligi uchun).

    Tahrirlab bo'lmasa (masalan, xabar video bo'lsa) — yangi xabar yuboradi."""
    if not callback.message:
        return
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as error:
        if "not modified" in str(error):
            return
        await callback.message.answer(text, reply_markup=markup)


def movie_buttons(movies, with_views: bool = False) -> list[list[InlineKeyboardButton]]:
    rows = []
    for movie in movies:
        label = movie["title"][:36] or movie["code"]
        if with_views:
            label += f" · {movie['views']} 👁"
        rows.append([InlineKeyboardButton(text=f"🎬 {label}", callback_data=f"get:{movie['id']}")])
    return rows


@router.callback_query(F.data == "u:home")
async def menu_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(
        callback,
        welcome(esc(callback.from_user.first_name)),
        user_menu_kb(is_admin(callback.from_user.id)),
    )


@router.callback_query(F.data.startswith("u:new:"))
async def menu_new(callback: CallbackQuery) -> None:
    total = await db.count_movies()
    await callback.answer()
    if total == 0:
        await show(callback, "🎬 Hozircha kinolar yo'q.", InlineKeyboardMarkup(inline_keyboard=[HOME_ROW]))
        return

    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(int(callback.data.split(":")[2]), pages - 1))
    movies = await db.list_movies(offset=page * PAGE_SIZE, limit=PAGE_SIZE)

    rows = movie_buttons(movies)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"u:new:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"u:new:{page + 1}"))
    rows.append(nav)
    rows.append(HOME_ROW)
    await show(
        callback,
        "🆕 <b>Yangi kinolar</b>\n\nKinoni tanlang 👇",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "u:top")
async def menu_top(callback: CallbackQuery) -> None:
    movies = await db.top_movies(PAGE_SIZE)
    await callback.answer()
    if not movies:
        await show(callback, "🎬 Hozircha kinolar yo'q.", InlineKeyboardMarkup(inline_keyboard=[HOME_ROW]))
        return
    await show(
        callback,
        "🔥 <b>Eng ko'p ko'rilgan kinolar</b>\n\nKinoni tanlang 👇",
        InlineKeyboardMarkup(inline_keyboard=[*movie_buttons(movies, with_views=True), HOME_ROW]),
    )


@router.callback_query(F.data == "u:genres")
async def menu_genres(callback: CallbackQuery) -> None:
    genres = await db.genre_counts()
    await callback.answer()
    if not genres:
        await show(callback, "🎞 Janrlar hali belgilanmagan.", InlineKeyboardMarkup(inline_keyboard=[HOME_ROW]))
        return
    buttons = [
        InlineKeyboardButton(text=f"🎞 {row['genre'][:24]} ({row['n']})", callback_data=f"u:g:{index}")
        for index, row in enumerate(genres)
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(HOME_ROW)
    await show(
        callback,
        "🎞 <b>Janrlar</b>\n\nJanrni tanlang 👇",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("u:g:"))
async def menu_genre(callback: CallbackQuery) -> None:
    index = int(callback.data.split(":")[2])
    genres = await db.genre_counts()
    if index >= len(genres):
        await callback.answer("Janrlar ro'yxati yangilangan, qaytadan oching.", show_alert=True)
        return
    genre = genres[index]["genre"]
    movies = await db.movies_by_genre(genre)
    await callback.answer()
    back = [InlineKeyboardButton(text="◀️ Janrlar", callback_data="u:genres")]
    await show(
        callback,
        f"🎞 <b>{esc(genre)}</b>\n\nKinoni tanlang 👇",
        InlineKeyboardMarkup(inline_keyboard=[*movie_buttons(movies), back, HOME_ROW]),
    )


@router.callback_query(F.data == "u:find")
async def menu_find(callback: CallbackQuery) -> None:
    await callback.answer()
    await show(
        callback,
        "🔎 <b>Qidirish</b>\n\nKino <b>kodini</b> yoki <b>nomini</b> yozib yuboring.\n"
        "Masalan: <code>101</code> yoki <code>Titanik</code>",
        InlineKeyboardMarkup(inline_keyboard=[HOME_ROW]),
    )


@router.callback_query(F.data == "u:help")
async def menu_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await show(callback, HELP, InlineKeyboardMarkup(inline_keyboard=[HOME_ROW]))
