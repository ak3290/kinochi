from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MessageOriginChannel

from config import ADMINS
from database import db
from keyboards import (
    ANNOUNCE_REQUEST_ID,
    BTN_ADD_MOVIE,
    BTN_ANNOUNCE,
    BTN_ADMIN,
    BTN_BACK,
    BTN_CANCEL,
    BTN_CHANNELS,
    BTN_EMOJI,
    BTN_MOVIES,
    BTN_SKIP,
    BTN_STATS,
    BTN_TEMPLATE,
    MENU_BUTTONS,
    PAGE_SIZE,
    admin_menu,
    admin_panel_kb,
    announce_kb,
    back_kb,
    cancel_menu,
    channels_kb,
    confirm_delete_kb,
    edit_movie_kb,
    emoji_kb,
    found_movies_kb,
    main_menu,
    movie_manage_kb,
    movies_list_kb,
    select_channel_menu,
    step_menu,
    template_kb,
    watch_kb,
)
from .menu import show
from states import (
    AddChannel,
    AddMovie,
    EditMovie,
    EditTemplate,
    FindMovie,
    SetAnnounce,
    SetEmoji,
    SetSticker,
)
from utils import (
    ANNOUNCE_KEY,
    CAPTION_LIMIT,
    DEFAULT_TEMPLATE,
    EMOJI_DEFAULTS,
    EMOJI_IDS,
    EMOJI_KEY,
    EMOJI_PLACEHOLDERS,
    EMOJI_TITLES,
    PLACEHOLDER_RE,
    PLACEHOLDERS,
    STICKER_KEY,
    TEMPLATE_KEY,
    announce_caption,
    emoji_html,
    esc,
    movie_info,
    set_emoji_ids,
    set_template,
    template_preview,
)

from .search import send_movie

logger = logging.getLogger(__name__)

router = Router()
# Butun router faqat adminlar uchun ishlaydi
router.message.filter(F.from_user.id.in_(ADMINS))
router.callback_query.filter(F.from_user.id.in_(ADMINS))

FIELD_NAMES = {
    "code": "kod",
    "title": "nom",
    "language": "til",
    "quality": "sifat",
    "genre": "janr",
    "category": "kategoriya",
    "caption": "tavsif",
}


@dataclass(frozen=True)
class Step:
    """Kino qo'shishda ketma-ket so'raladigan maydon."""

    name: str
    prompt: str
    options: tuple[str, ...] = ()
    required: bool = False


STEPS: tuple[Step, ...] = (
    Step("title", "🍿 <b>Kino nomini</b> yuboring:", required=True),
    Step(
        "language",
        "🇺🇿 <b>Tilini</b> yuboring:",
        ("O'zbek tilida", "Rus tilida", "Ingliz tilida", "O'zbek subtitr"),
    ),
    Step("quality", "💾 <b>Sifatini</b> yuboring:", ("480p", "720p", "1080p", "4K")),
    Step("genre", "🎞️ <b>Janrini</b> yuboring (masalan: Romantic komediya):"),
    Step("category", "⛔️ <b>Ko'rish kategoriyasini</b> yuboring:", ("6+", "12+", "16+", "18+")),
)

TOTAL_STEPS = len(STEPS) + 2  # + poster + kod


def progress(number: int) -> str:
    return f"<i>Qadam {number}/{TOTAL_STEPS}</i>\n\n"


STEP_OPTIONS: dict[str, tuple[str, ...]] = {step.name: step.options for step in STEPS}

# Admin shablonda HTML teglarini qo'lda yozganini aniqlash uchun
HTML_TAG_RE = re.compile(r"</?(b|strong|i|em|u|s|code|pre|a|tg-spoiler|blockquote)\b", re.I)


# ---------- panel ----------


async def panel_text() -> str:
    return (
        "🛠 <b>Admin panel</b>\n\n"
        f"<blockquote>🎬 Kinolar: <b>{await db.count_movies()}</b>\n"
        f"👥 Foydalanuvchilar: <b>{await db.count_users()}</b></blockquote>\n\n"
        "Kerakli bo'limni tanlang 👇"
    )


@router.message(F.text == BTN_ADMIN)
async def open_panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(await panel_text(), reply_markup=admin_panel_kb())


@router.message(F.text == BTN_BACK)
async def close_panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id))


@router.message(F.text == BTN_CANCEL)
@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(await panel_text(), reply_markup=admin_panel_kb())
        return
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=admin_menu())
    await message.answer(await panel_text(), reply_markup=admin_panel_kb())


# ---------- kino qo'shish ----------


@router.message(F.text == BTN_ADD_MOVIE)
async def add_movie_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddMovie.video)
    await message.answer(
        "🎬 Avval kinoning <b>o'zini</b> (video yoki fayl) yuboring.\n\n"
        "Keyin nomi, tili, sifati, janri, kategoriyasi va posteri (rasm) ketma-ket so'raladi.",
        reply_markup=cancel_menu(),
    )


@router.message(AddMovie.video, F.video | F.document | F.animation)
async def add_movie_file(message: Message, state: FSMContext) -> None:
    if message.video:
        file_id, file_type = message.video.file_id, "video"
    elif message.animation:
        file_id, file_type = message.animation.file_id, "animation"
    else:
        file_id, file_type = message.document.file_id, "document"

    await state.update_data(file_id=file_id, file_type=file_type, step=0)
    await state.set_state(AddMovie.field)
    await message.answer("✅ Fayl qabul qilindi.")
    await ask_step(message, 0)


@router.message(AddMovie.video)
async def add_movie_wrong(message: Message) -> None:
    await message.answer("⚠️ Iltimos, video yoki fayl yuboring.")


async def ask_step(message: Message, index: int) -> None:
    step = STEPS[index]
    hint = "" if step.required else f"\n\n<i>Kerak bo'lmasa — «{BTN_SKIP}»</i>"
    await message.answer(
        f"{progress(index + 1)}{step.prompt}{hint}",
        reply_markup=step_menu(step.options, skip=not step.required),
    )


@router.message(AddMovie.field, F.text)
async def add_movie_field(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    index = data.get("step", 0)
    step = STEPS[index]
    value = message.text.strip()

    if value == BTN_SKIP:
        if step.required:
            await message.answer("⚠️ Bu maydon majburiy, o'tkazib yuborib bo'lmaydi.")
            return
        value = ""

    await state.update_data(**{step.name: value}, step=index + 1)

    if index + 1 < len(STEPS):
        await ask_step(message, index + 1)
        return

    await state.set_state(AddMovie.poster)
    await message.answer(
        f"{progress(len(STEPS) + 1)}🖼 Kino <b>posterini</b> (rasm) yuboring — u kanaldagi e'londa chiqadi.\n\n"
        f"<i>Kerak bo'lmasa — «{BTN_SKIP}»</i>",
        reply_markup=step_menu((), skip=True),
    )


@router.message(AddMovie.field)
async def add_movie_field_wrong(message: Message) -> None:
    await message.answer("⚠️ Javobni matn ko'rinishida yuboring.")


async def ask_code(message: Message, state: FSMContext) -> None:
    await state.set_state(AddMovie.code)
    await message.answer(
        f"{progress(TOTAL_STEPS)}🗂 Oxirgi qadam — kino <b>kodini</b> yuboring (masalan: <code>1320</code>).\n"
        "Foydalanuvchi shu kodni yozib kinoni topadi.",
        reply_markup=cancel_menu(),
    )


@router.message(AddMovie.poster, F.photo)
async def add_movie_poster(message: Message, state: FSMContext) -> None:
    await state.update_data(poster_id=message.photo[-1].file_id)
    await message.answer("✅ Poster qabul qilindi.")
    await ask_code(message, state)


@router.message(AddMovie.poster, F.text == BTN_SKIP)
async def add_movie_poster_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(poster_id="")
    await ask_code(message, state)


@router.message(AddMovie.poster)
async def add_movie_poster_wrong(message: Message) -> None:
    await message.answer(
        f"⚠️ Iltimos, rasm yuboring (rasm sifatida, fayl emas) yoki «{BTN_SKIP}» ni bosing."
    )


@router.message(AddMovie.code, F.text)
async def add_movie_code(message: Message, state: FSMContext, bot: Bot) -> None:
    code = message.text.strip()
    if len(code) > 32 or "\n" in code:
        await message.answer("⚠️ Kod juda uzun. 32 belgigacha bo'lgan kod yuboring.")
        return

    if await db.get_movie_by_code(code):
        await message.answer(
            f"⚠️ <code>{esc(code)}</code> kodi allaqachon band. Boshqa kod yuboring."
        )
        return

    data = await state.get_data()
    added = await db.add_movie(
        code=code,
        title=data.get("title", ""),
        language=data.get("language", ""),
        quality=data.get("quality", ""),
        genre=data.get("genre", ""),
        category=data.get("category", ""),
        poster_id=data.get("poster_id", ""),
        file_id=data["file_id"],
        file_type=data["file_type"],
    )
    await state.clear()

    if not added:
        await message.answer("⚠️ Kod band ekan, qaytadan urinib ko'ring.", reply_markup=admin_menu())
        return

    movie = await db.get_movie_by_code(code)
    await message.answer(
        "✅ Kino saqlandi! Foydalanuvchi uni shunday ko'radi:", reply_markup=admin_menu()
    )
    await send_movie(message, movie, count_view=False)

    status = await announce_movie(bot, movie)
    if status:
        await message.answer(status)


@router.message(AddMovie.code)
async def add_movie_code_wrong(message: Message) -> None:
    await message.answer("⚠️ Kodni matn ko'rinishida yuboring.")


# ---------- statistika ----------


async def stats_text() -> str:
    users = await db.count_users()
    today = await db.count_users_since(1)
    week = await db.count_users_since(7)
    movies = await db.count_movies()
    views = await db.total_views()
    channels = await db.count_channels()
    top = await db.top_movies(5)

    text = (
        "📊 <b>Umumiy statistika</b>\n\n"
        f"<blockquote>👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"➕ Bugun qo'shilgan: <b>{today}</b>\n"
        f"📅 Hafta davomida: <b>{week}</b></blockquote>\n\n"
        f"<blockquote>🎬 Kinolar: <b>{movies}</b>\n"
        f"👁 Jami ko'rishlar: <b>{views}</b>\n"
        f"📢 Majburiy kanallar: <b>{channels}</b></blockquote>"
    )
    if top:
        rows = "\n".join(
            f"{i}. {esc(m['title'] or m['code'])} — {m['views']} 👁"
            for i, m in enumerate(top, start=1)
        )
        text += f"\n\n🔥 <b>Eng ko'p ko'rilganlar:</b>\n<blockquote>{rows}</blockquote>"
    return text


@router.message(F.text == BTN_STATS)
async def stats(message: Message) -> None:
    await message.answer(await stats_text(), reply_markup=back_kb())


# ---------- kinolar ro'yxati ----------


async def render_page(page: int) -> tuple[str, object | None]:
    total = await db.count_movies()
    if total == 0:
        return "🎬 Hozircha bazada kino yo'q.", back_kb()

    page = max(0, min(page, (total - 1) // PAGE_SIZE))
    movies = await db.list_movies(offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    text = (
        f"🎬 <b>Kinolar</b> (jami: {total})\n\n"
        "Tahrirlash yoki o'chirish uchun ro'yxatdan tanlang.\n"
        "Tezroq yo'l — kino <b>kodini</b> yoki <b>nomini</b> shu yerga yozib yuboring."
    )
    return text, movies_list_kb(movies, page, total)


@router.message(F.text == BTN_MOVIES)
async def movies_list(message: Message, state: FSMContext) -> None:
    # Ro'yxat ochiq turganda yozilgan matn kod/nom bo'yicha qidiruv sifatida qabul qilinadi
    await state.set_state(FindMovie.query)
    text, markup = await render_page(0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "find")
async def movie_find_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FindMovie.query)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "🔎 Kino <b>kodini</b> (masalan: <code>1320</code>) yoki <b>nomini</b> yuboring:",
            reply_markup=cancel_menu(),
        )


@router.message(FindMovie.query, F.text, ~F.text.in_(MENU_BUTTONS))
async def movie_find(message: Message, state: FSMContext) -> None:
    query = message.text.strip()

    movie = await db.get_movie_by_code(query)
    if movie:
        await state.clear()
        await message.answer(movie_info(movie), reply_markup=movie_manage_kb(movie["id"], 0))
        return

    movies = await db.search_movies(query, limit=20)
    if not movies:
        await message.answer(
            f"😔 «{esc(query)}» bo'yicha hech narsa topilmadi.\n"
            "Boshqa kod yoki nom yuboring."
        )
        return

    if len(movies) == 1:
        await state.clear()
        await message.answer(
            movie_info(movies[0]), reply_markup=movie_manage_kb(movies[0]["id"], 0)
        )
        return

    await message.answer(
        f"🔎 «{esc(query)}» bo'yicha {len(movies)} ta natija:",
        reply_markup=found_movies_kb(movies),
    )


@router.callback_query(F.data.startswith("page:"))
async def movies_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    text, markup = await render_page(page)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("movie:"))
async def movie_detail(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    _, movie_id, page = callback.data.split(":")
    movie = await db.get_movie(int(movie_id))
    if not movie:
        await callback.answer("Bu kino topilmadi.", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            movie_info(movie), reply_markup=movie_manage_kb(int(movie_id), int(page))
        )


# ---------- o'chirish ----------


@router.callback_query(F.data.startswith("del:"))
async def movie_delete_confirm(callback: CallbackQuery) -> None:
    _, movie_id, page = callback.data.split(":")
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "🗑 Ushbu kino o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.",
            reply_markup=confirm_delete_kb(int(movie_id), int(page)),
        )


@router.callback_query(F.data.startswith("delyes:"))
async def movie_delete(callback: CallbackQuery) -> None:
    _, movie_id, page = callback.data.split(":")
    await db.delete_movie(int(movie_id))
    await callback.answer("🗑 O'chirildi", show_alert=True)
    text, markup = await render_page(int(page))
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("annsend:"))
async def movie_announce(callback: CallbackQuery, bot: Bot) -> None:
    movie = await db.get_movie(int(callback.data.split(":")[1]))
    if not movie:
        await callback.answer("Bu kino topilmadi.", show_alert=True)
        return
    await callback.answer()
    status = await announce_movie(bot, movie)
    if callback.message:
        await callback.message.answer(
            status or "⚠️ E'lon kanali tanlanmagan. «📣 E'lon kanali» bo'limidan tanlang."
        )


# ---------- tahrirlash ----------


@router.callback_query(F.data.startswith("edit:"))
async def movie_edit_menu(callback: CallbackQuery) -> None:
    _, movie_id, page = callback.data.split(":")
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "✏️ Qaysi maydonni tahrirlaysiz?",
            reply_markup=edit_movie_kb(int(movie_id), int(page)),
        )


@router.callback_query(F.data.startswith("field:"))
async def movie_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    _, field, movie_id, page = callback.data.split(":")
    await state.set_state(EditMovie.value)
    await state.update_data(field=field, movie_id=int(movie_id), page=int(page))
    await callback.answer()
    if callback.message:
        options = STEP_OPTIONS.get(field, ())
        can_skip = field not in {"code", "title"}
        hint = f"\n\n<i>Bo'sh qoldirish uchun — «{BTN_SKIP}»</i>" if can_skip else ""
        await callback.message.answer(
            f"✏️ Yangi <b>{FIELD_NAMES[field]}</b> ni yuboring:{hint}",
            reply_markup=step_menu(options, skip=can_skip),
        )


@router.message(EditMovie.value, F.text)
async def movie_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field, movie_id, page = data["field"], data["movie_id"], data["page"]
    value = message.text.strip()

    if value == BTN_SKIP:
        if field in {"code", "title"}:
            await message.answer("⚠️ Bu maydonni bo'sh qoldirib bo'lmaydi.")
            return
        value = ""

    if field == "code":
        existing = await db.get_movie_by_code(value)
        if existing and existing["id"] != movie_id:
            await message.answer("⚠️ Bu kod band. Boshqa kod yuboring.")
            return

    updated = await db.update_movie_field(movie_id, field, value)
    await state.clear()
    if not updated:
        await message.answer("⚠️ Saqlab bo'lmadi. Qaytadan urinib ko'ring.", reply_markup=admin_menu())
        return

    movie = await db.get_movie(movie_id)
    await message.answer("✅ Yangilandi.", reply_markup=admin_menu())
    if movie:
        await message.answer(movie_info(movie), reply_markup=movie_manage_kb(movie_id, page))


@router.message(EditMovie.value)
async def movie_edit_value_wrong(message: Message) -> None:
    await message.answer("⚠️ Qiymatni matn ko'rinishida yuboring.")


# ---------- caption shabloni ----------


async def template_text() -> tuple[str, bool]:
    saved = await db.get_setting(TEMPLATE_KEY)
    current = saved or DEFAULT_TEMPLATE
    hints = "\n".join(f"<code>{{{key}}}</code> — {name}" for key, name in PLACEHOLDERS.items())
    text = (
        f"🧩 <b>Caption shabloni</b> "
        f"({'o‘zgartirilgan' if saved else 'standart'})\n\n"
        f"<b>Hozirgi ko'rinishi:</b>\n{template_preview(current)}\n\n"
        f"<b>Shablon matni:</b>\n<pre>{esc(current)}</pre>\n\n"
        f"<b>O'rin egallovchilar:</b>\n{hints}\n\n"
        "<b>Emoji o'rinlari</b> (premium emoji bilan almashadi): "
        + ", ".join(f"<code>{{{key}}}</code>" for key in EMOJI_PLACEHOLDERS)
        + "\n\n"
        "<i>Qiymati bo'sh bo'lgan o'rin egallovchi turgan qator umuman chiqmaydi.</i>"
    )
    return text, bool(saved)


@router.message(F.text == BTN_TEMPLATE)
async def template_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, is_custom = await template_text()
    await message.answer(text, reply_markup=template_kb(is_custom))


@router.callback_query(F.data == "tpl_edit")
async def template_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditTemplate.value)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "✏️ Yangi shablonni yuboring.\n\n"
            "Telegram'ning o'z formatlashidan foydalaning (<b>qalin</b>, <i>kursiv</i>, "
            "<code>monospace</code>) — u avtomatik saqlanadi.\n"
            f"O'rin egallovchilar: {', '.join('{' + key + '}' for key in PLACEHOLDERS)}",
            reply_markup=cancel_menu(),
        )


@router.message(EditTemplate.value, F.text)
async def template_save(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    # Admin HTML teglarini o'zi yozgan bo'lsa — o'sha holicha, aks holda
    # Telegram'dagi formatlashini (qalin, kursiv) HTML ga o'giramiz
    template = raw if HTML_TAG_RE.search(raw) else message.html_text.strip()

    unknown = {
        name
        for name in PLACEHOLDER_RE.findall(template)
        if name not in PLACEHOLDERS and name not in EMOJI_PLACEHOLDERS
    }
    if unknown:
        await message.answer(
            "⚠️ Noma'lum o'rin egallovchi: "
            + ", ".join(f"<code>{{{esc(name)}}}</code>" for name in sorted(unknown))
            + "\nRuxsat etilganlar: "
            + ", ".join(f"<code>{{{key}}}</code>" for key in PLACEHOLDERS)
        )
        return

    preview = template_preview(template)
    if len(preview) > CAPTION_LIMIT:
        await message.answer(
            f"⚠️ Shablon juda uzun ({len(preview)} belgi). "
            f"Telegram caption uchun {CAPTION_LIMIT} belgidan oshmasligi kerak."
        )
        return

    # Saqlashdan oldin HTML to'g'riligini Telegram'ning o'zida tekshiramiz
    try:
        await message.answer(preview)
    except TelegramBadRequest as error:
        logger.warning("Shablon HTML xatosi: %s", error)
        await message.answer(
            "❌ Shablonni Telegram qabul qilmadi — HTML teglarida xato bor.\n\n"
            f"<code>{esc(str(error))}</code>\n\n"
            "Teglar juftlanganini tekshiring: <code>&lt;b&gt;...&lt;/b&gt;</code>"
        )
        return

    await db.set_setting(TEMPLATE_KEY, template)
    set_template(template)
    await state.clear()
    await message.answer("☝️ Shablon saqlandi, kinolar shu ko'rinishda yuboriladi.",
                         reply_markup=admin_menu())


@router.message(EditTemplate.value)
async def template_save_wrong(message: Message) -> None:
    await message.answer("⚠️ Shablonni matn ko'rinishida yuboring.")


@router.callback_query(F.data == "tpl_reset")
async def template_reset(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await db.delete_setting(TEMPLATE_KEY)
    set_template("")
    await callback.answer("♻️ Standart shablon qaytarildi", show_alert=True)
    text, is_custom = await template_text()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=template_kb(is_custom))


# ---------- kanalga e'lon ----------


async def announce_movie(bot: Bot, movie) -> str:
    """Yangi kino haqida e'lon kanalga post qiladi.

    Qaytaradi: adminga ko'rsatiladigan natija matni ('' — e'lon kanali sozlanmagan).
    """
    raw = await db.get_setting(ANNOUNCE_KEY)
    if not raw:
        return ""
    chat_id = int(raw)

    from utils import BOT_USERNAME as username  # bot ishga tushganda to'ldirilgan qiymat

    caption = announce_caption(movie)
    markup = (
        watch_kb(f"https://t.me/{username}?start=m{movie['id']}") if username else None
    )
    try:
        if movie["poster_id"]:
            await bot.send_photo(chat_id, movie["poster_id"], caption=caption, reply_markup=markup)
        else:
            await bot.send_message(chat_id, caption, reply_markup=markup)
    except TelegramAPIError as error:
        logger.warning("E'lonni kanalga yuborib bo'lmadi (%s): %s", chat_id, error)
        return (
            "⚠️ Kino saqlandi, lekin kanalga e'lon yuborilmadi.\n"
            f"Sabab: <code>{esc(str(error))}</code>\n"
            "Bot kanalda <b>admin</b> va «Post messages» huquqiga ega ekanini tekshiring."
        )
    return "📣 E'lon kanalga yuborildi."


async def announce_text() -> tuple[str, bool]:
    raw = await db.get_setting(ANNOUNCE_KEY)
    if not raw:
        return (
            "📣 <b>E'lon kanali</b>\n\nHozircha tanlanmagan. Kanal tanlansa, har bir yangi kino "
            "qo'shilganda shu kanalga rasm va ma'lumotlar bilan e'lon yuboriladi.",
            False,
        )
    return f"📣 <b>E'lon kanali</b>\n\nHozirgi kanal: <code>{raw}</code>", True


@router.message(F.text == BTN_ANNOUNCE)
async def announce_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, is_set = await announce_text()
    await message.answer(text, reply_markup=announce_kb(is_set))


@router.callback_query(F.data == "ann_set")
async def announce_set_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetAnnounce.channel)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "📢 Pastdagi <b>«Kanalni tanlash»</b> tugmasini bosing yoki kanal "
            "<code>@username</code> / ID'sini yuboring.\n\n"
            "⚠️ Bot kanalda <b>admin</b> bo'lib, xabar yuborish huquqiga ega bo'lishi shart.",
            reply_markup=select_channel_menu(ANNOUNCE_REQUEST_ID),
        )


@router.callback_query(F.data == "ann_off")
async def announce_off(callback: CallbackQuery) -> None:
    await db.delete_setting(ANNOUNCE_KEY)
    await callback.answer("🗑 E'lon kanali o'chirildi", show_alert=True)
    text, is_set = await announce_text()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=announce_kb(is_set))


# ---------- majburiy obuna kanallari ----------


async def channels_text() -> str:
    channels = await db.list_channels()
    if not channels:
        return "📢 <b>Majburiy obuna</b>\n\nHozircha kanal qo'shilmagan."
    rows = "\n".join(
        f"{i}. {esc(ch['title'] or '—')} "
        f"({'@' + ch['username'] if ch['username'] else ch['chat_id']})"
        for i, ch in enumerate(channels, start=1)
    )
    return (
        f"📢 <b>Majburiy obuna kanallari</b>\n\n{rows}\n\n"
        "O'chirish uchun kanal ustiga bosing."
    )


@router.message(F.text == BTN_CHANNELS)
async def channels_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(await channels_text(), reply_markup=channels_kb(await db.list_channels()))


@router.callback_query(F.data == "chadd")
async def channel_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddChannel.channel)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "📢 Pastdagi <b>«Kanalni tanlash»</b> tugmasini bosing va ro'yxatdan "
            "kerakli kanalni tanlang.\n\n"
            "Yoki qo'lda yuboring:\n"
            "• kanal username'i: <code>@kanal_nomi</code>\n"
            "• kanal ID'si: <code>-1001234567890</code>\n"
            "• kanaldan biror postni <b>forward</b> qiling\n\n"
            "⚠️ Bot kanalda <b>admin</b> bo'lishi shart!",
            reply_markup=select_channel_menu(),
        )


@router.message(AddChannel.channel, F.chat_shared)
async def channel_add_shared(message: Message, state: FSMContext, bot: Bot) -> None:
    """Admin «Kanalni tanlash» tugmasi orqali kanalni tanlaganda."""
    shared = message.chat_shared
    await save_channel(
        message, state, bot, shared.chat_id, shared_title=shared.title or ""
    )


@router.message(AddChannel.channel)
async def channel_add_manual(message: Message, state: FSMContext, bot: Bot) -> None:
    """Username, ID yoki forward orqali qo'shish."""
    origin = message.forward_origin
    if isinstance(origin, MessageOriginChannel):
        target: str | int = origin.chat.id
    elif message.text:
        text = message.text.strip()
        target = int(text) if text.lstrip("-").isdigit() else text
    else:
        await message.answer(
            "⚠️ «Kanalni tanlash» tugmasidan foydalaning yoki kanal username'i, "
            "ID'si yoxud forward qilingan postni yuboring."
        )
        return

    await save_channel(message, state, bot, target)


async def save_channel(
    message: Message,
    state: FSMContext,
    bot: Bot,
    target: str | int,
    shared_title: str = "",
) -> None:
    label = f"«{esc(shared_title)}»" if shared_title else f"<code>{target}</code>"
    try:
        chat = await bot.get_chat(target)
        me = await bot.get_chat_member(chat.id, bot.id)
    except TelegramAPIError as error:
        logger.warning("Kanalni olishda xatolik (%s): %s", target, error)
        await message.answer(
            f"❌ {label} kanaliga bot kira olmadi.\n\n"
            f"Sabab (Telegram javobi): <code>{esc(str(error))}</code>\n\n"
            "👉 Nima qilish kerak:\n"
            "1. Kanalni oching → <b>Administrators</b> → <b>Add Admin</b>\n"
            f"2. Botni (@{(await bot.me()).username}) admin qilib qo'shing\n"
            "3. Shundan keyin kanalni yana tanlang\n\n"
            "⚠️ Botni oddiy <b>obunachi</b> qilib qo'shish yetarli emas — "
            "u <b>admin</b> bo'lishi shart."
        )
        return

    if me.status not in {"administrator", "creator"}:
        await message.answer(
            f"❌ Bot {label} kanalida admin emas (hozirgi holati: <code>{me.status}</code>).\n"
            "Kanal sozlamalarida botni administrator qilib qo'ying va qaytadan tanlang."
        )
        return

    invite_link = chat.invite_link
    if not chat.username and not invite_link:
        try:
            link = await bot.create_chat_invite_link(chat.id, name="Kinochi bot")
            invite_link = link.invite_link
        except TelegramAPIError as error:
            logger.warning("Invite link yaratib bo'lmadi (%s): %s", chat.id, error)

    if not chat.username and not invite_link:
        await message.answer(
            "❌ Kanal uchun havola olinmadi. Botga «Invite Users via Link» huquqini bering."
        )
        return

    await db.add_channel(chat.id, chat.title or "", chat.username, invite_link)
    await state.clear()
    await message.answer(
        f"✅ <b>{esc(chat.title or '')}</b> majburiy obunaga qo'shildi.",
        reply_markup=admin_menu(),
    )
    await message.answer(await channels_text(), reply_markup=channels_kb(await db.list_channels()))


@router.callback_query(F.data.startswith("chdel:"))
async def channel_delete(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[1])
    await db.delete_channel(chat_id)
    await callback.answer("🗑 Kanal o'chirildi", show_alert=True)
    if callback.message:
        await callback.message.edit_text(
            await channels_text(), reply_markup=channels_kb(await db.list_channels())
        )


@router.message(SetAnnounce.channel, F.chat_shared)
async def announce_shared(message: Message, state: FSMContext, bot: Bot) -> None:
    await save_announce(message, state, bot, message.chat_shared.chat_id)


@router.message(SetAnnounce.channel)
async def announce_manual(message: Message, state: FSMContext, bot: Bot) -> None:
    origin = message.forward_origin
    if isinstance(origin, MessageOriginChannel):
        target: str | int = origin.chat.id
    elif message.text:
        text = message.text.strip()
        target = int(text) if text.lstrip("-").isdigit() else text
    else:
        await message.answer("⚠️ «Kanalni tanlash» tugmasidan foydalaning yoki @username yuboring.")
        return
    await save_announce(message, state, bot, target)


async def save_announce(message: Message, state: FSMContext, bot: Bot, target: str | int) -> None:
    try:
        chat = await bot.get_chat(target)
        me = await bot.get_chat_member(chat.id, bot.id)
    except TelegramAPIError as error:
        logger.warning("E'lon kanalini olishda xatolik (%s): %s", target, error)
        await message.answer(
            "❌ Bot kanalga kira olmadi.\n\n"
            f"Sabab: <code>{esc(str(error))}</code>\n\n"
            "Botni kanalga <b>admin</b> qilib qo'shing va qaytadan urinib ko'ring."
        )
        return

    if me.status not in {"administrator", "creator"}:
        await message.answer(
            f"❌ Bot bu kanalda admin emas (holati: <code>{me.status}</code>). "
            "Administrator qilib qo'ying va qaytadan tanlang."
        )
        return
    if me.status == "administrator" and getattr(me, "can_post_messages", True) is False:
        await message.answer("❌ Botga «Post messages» (xabar yuborish) huquqini bering.")
        return

    await db.set_setting(ANNOUNCE_KEY, str(chat.id))
    await state.clear()
    await message.answer(
        f"✅ E'lon kanali: <b>{esc(chat.title or '')}</b>.\n"
        "Endi har bir yangi kino shu kanalga e'lon qilinadi.",
        reply_markup=admin_menu(),
    )


# ---------- premium emoji va stiker ----------


def pick_custom_emoji_id(message: Message) -> str:
    """Xabardagi birinchi premium emoji ID'si (emoji yoki emoji-stiker)."""
    if message.sticker and message.sticker.custom_emoji_id:
        return message.sticker.custom_emoji_id
    for entity in message.entities or []:
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            return entity.custom_emoji_id
    return ""


async def emoji_panel() -> tuple[str, object]:
    sticker = await db.get_setting(STICKER_KEY)
    lines = "\n".join(
        f"{emoji_html(key)} {EMOJI_TITLES[key]} — "
        f"{'✅ premium' if key in EMOJI_IDS else 'oddiy'}"
        for key in EMOJI_DEFAULTS
    )
    text = (
        "✨ <b>Premium emoji va stiker</b>\n\n"
        f"<blockquote>{lines}</blockquote>\n\n"
        f"🎭 Start stikeri: <b>{'✅ o‘rnatilgan' if sticker else 'yo‘q'}</b>\n\n"
        "<i>ℹ️ Premium emoji botdan faqat bot egasi Fragment'da qo'shimcha username "
        "sotib olgan bo'lsa ko'rinadi — aks holda oddiy emoji chiqadi (xato bermaydi). "
        "Stiker esa har qanday botda ishlaydi.</i>\n\n"
        "O'zgartirish uchun belgini tanlang 👇"
    )
    items = [
        (key, f"{EMOJI_DEFAULTS[key]} {EMOJI_TITLES[key]}{' ✅' if key in EMOJI_IDS else ''}")
        for key in EMOJI_DEFAULTS
    ]
    return text, emoji_kb(items, bool(EMOJI_IDS), bool(sticker))


async def save_emoji_ids() -> None:
    await db.set_setting(EMOJI_KEY, json.dumps(EMOJI_IDS))


@router.message(F.text == BTN_EMOJI)
async def emoji_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, markup = await emoji_panel()
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("emo:"))
async def emoji_pick(callback: CallbackQuery, state: FSMContext) -> None:
    name = callback.data.split(":")[1]
    if name not in EMOJI_DEFAULTS:
        await callback.answer()
        return
    await state.set_state(SetEmoji.value)
    await state.update_data(name=name)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"✨ «{EMOJI_TITLES[name]}» uchun <b>premium emoji</b> yuboring "
            "(bitta emoji yetarli).\n\n"
            "<i>Premium emoji ID'si avtomatik olinadi.</i>",
            reply_markup=cancel_menu(),
        )


@router.message(SetEmoji.value)
async def emoji_save(message: Message, state: FSMContext) -> None:
    emoji_id = pick_custom_emoji_id(message)
    if not emoji_id:
        await message.answer(
            "⚠️ Bu premium emoji emas. Premium emoji (animatsiyali) yuboring "
            "yoki «❌ Bekor qilish» ni bosing."
        )
        return
    name = (await state.get_data())["name"]
    EMOJI_IDS[name] = emoji_id
    await save_emoji_ids()
    await state.clear()
    text, markup = await emoji_panel()
    await message.answer(
        f"✅ «{EMOJI_TITLES[name]}» uchun premium emoji saqlandi.", reply_markup=admin_menu()
    )
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "emo_reset")
async def emoji_reset(callback: CallbackQuery) -> None:
    set_emoji_ids("")
    await db.delete_setting(EMOJI_KEY)
    await callback.answer("♻️ Oddiy emojilar qaytarildi", show_alert=True)
    text, markup = await emoji_panel()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "stk_set")
async def sticker_set_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetSticker.value)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "🎭 Istalgan <b>stikerni</b> yuboring — u /start bosganda xush kelibsiz "
            "xabaridan oldin chiqadi.",
            reply_markup=cancel_menu(),
        )


@router.message(SetSticker.value, F.sticker)
async def sticker_save(message: Message, state: FSMContext) -> None:
    await db.set_setting(STICKER_KEY, message.sticker.file_id)
    await state.clear()
    text, markup = await emoji_panel()
    await message.answer("✅ Start stikeri saqlandi.", reply_markup=admin_menu())
    await message.answer(text, reply_markup=markup)


@router.message(SetSticker.value)
async def sticker_wrong(message: Message) -> None:
    await message.answer("⚠️ Iltimos, stiker yuboring.")


@router.callback_query(F.data == "stk_off")
async def sticker_off(callback: CallbackQuery) -> None:
    await db.delete_setting(STICKER_KEY)
    await callback.answer("🗑 Stiker o'chirildi", show_alert=True)
    text, markup = await emoji_panel()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)



# ---------- admin panel: inline bo'limlar ----------


@router.callback_query(F.data == "adm:home")
async def hub_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(callback, await panel_text(), admin_panel_kb())


@router.callback_query(F.data == "adm:add")
async def hub_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.message:
        await add_movie_start(callback.message, state)


@router.callback_query(F.data == "adm:stats")
async def hub_stats(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(callback, await stats_text(), back_kb())


@router.callback_query(F.data == "adm:movies")
async def hub_movies(callback: CallbackQuery, state: FSMContext) -> None:
    # Ro'yxat ochiq turganda yozilgan matn kod/nom bo'yicha qidiruv sifatida qabul qilinadi
    await state.set_state(FindMovie.query)
    await callback.answer()
    text, markup = await render_page(0)
    await show(callback, text, markup)


@router.callback_query(F.data == "adm:channels")
async def hub_channels(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await show(callback, await channels_text(), channels_kb(await db.list_channels()))


@router.callback_query(F.data == "adm:tpl")
async def hub_template(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    text, is_custom = await template_text()
    await show(callback, text, template_kb(is_custom))


@router.callback_query(F.data == "adm:ann")
async def hub_announce(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    text, is_set = await announce_text()
    await show(callback, text, announce_kb(is_set))


@router.callback_query(F.data == "adm:emoji")
async def hub_emoji(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    text, markup = await emoji_panel()
    await show(callback, text, markup)
