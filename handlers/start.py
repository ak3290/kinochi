from __future__ import annotations

import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message, User

from database import db
from config import is_admin
from keyboards import user_menu_kb
from utils import STICKER_KEY, emoji_html, esc, unsubscribed_channels

from .search import send_movie

router = Router()

def welcome(name: str) -> str:
    return (
        f"{emoji_html('film')} <b>Kinochi botga xush kelibsiz, {name}!</b>\n\n"
        "Kino topish juda oson:\n"
        "▫️ kino <b>kodini</b> yuboring — masalan: <code>101</code>\n"
        "▫️ yoki kino <b>nomini</b> yozing — masalan: <code>Titanik</code>"
    )


async def send_welcome(message: Message, user: User) -> None:
    """Start stikeri (bo'lsa) + xush kelibsiz xabari."""
    sticker = await db.get_setting(STICKER_KEY)
    if sticker:
        try:
            await message.answer_sticker(sticker)
        except TelegramAPIError:
            pass  # stiker yuborilmasa ham xush kelibsiz xabari ketaveradi
    await message.answer(welcome(esc(user.first_name)), reply_markup=user_menu_kb(is_admin(user.id)))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject) -> None:
    await state.clear()
    await db.add_user(
        message.from_user.id,
        message.from_user.full_name,
        message.from_user.username,
    )

    # Kanal postidagi «Kinoni ko'rish» tugmasi: /start m<id>
    match = re.fullmatch(r"m(\d+)", command.args or "")
    if match:
        movie = await db.get_movie(int(match.group(1)))
        if movie:
            await send_movie(message, movie)
        else:
            await message.answer("😔 Bu kino topilmadi yoki o'chirilgan.")
        return

    await send_welcome(message, message.from_user)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "Kino kodini yoki nomini yuboring — bot uni topib beradi.\n"
        "/start — bosh menyu"
    )


@router.callback_query(F.data == "check_subs")
async def check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    channels = await unsubscribed_channels(bot, callback.from_user.id)
    if channels:
        await callback.answer("❌ Siz hali barcha kanallarga obuna bo'lmadingiz.", show_alert=True)
        return

    await callback.answer("✅ Rahmat! Endi botdan foydalanishingiz mumkin.", show_alert=True)
    await db.add_user(
        callback.from_user.id,
        callback.from_user.full_name,
        callback.from_user.username,
    )
    if callback.message:
        await callback.message.delete()
        await send_welcome(callback.message, callback.from_user)


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()
