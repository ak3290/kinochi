from __future__ import annotations

import html
import json
import logging
import re

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from database import db

logger = logging.getLogger(__name__)

SUBSCRIBED_STATUSES = {"member", "administrator", "creator"}


async def unsubscribed_channels(bot: Bot, user_id: int) -> list:
    """Foydalanuvchi obuna bo'lmagan majburiy kanallar ro'yxati."""
    result = []
    for channel in await db.list_channels():
        try:
            member = await bot.get_chat_member(channel["chat_id"], user_id)
        except TelegramAPIError as error:
            # Bot kanalda admin emas yoki kanal o'chirilgan — foydalanuvchini bloklamaymiz
            logger.warning("Kanalni tekshirib bo'lmadi (%s): %s", channel["chat_id"], error)
            continue
        if member.status not in SUBSCRIBED_STATUSES:
            result.append(channel)
    return result


SEPARATOR = "➖➖➖➖➖➖➖➖➖➖➖➖"

DEFAULT_TEMPLATE = (
    "{e_film} <b>{nom}</b>\n"
    f"{SEPARATOR}\n"
    "{tavsif}\n"
    "{e_til} Tili: <b>{til}</b>\n"
    "{e_sifat} Sifati: <b>{sifat}</b>\n"
    "{e_janr} Janri: <b>{janr}</b>\n"
    "{e_kat} Kategoriya: <b>{kategoriya}</b>\n"
    f"{SEPARATOR}\n"
    "{e_kod} Kod: <code>{kod}</code>\n"
    "{e_kor} Ko'rildi: {korishlar} marta\n"
    "{e_bot} {bot}"
)

# Har bir o'rin egallovchi va uning izohi (admin panelda ko'rsatiladi)
PLACEHOLDERS = {
    "nom": "kino nomi",
    "til": "tili",
    "sifat": "sifati",
    "janr": "janri",
    "kategoriya": "ko'rish kategoriyasi",
    "kod": "kino kodi",
    "korishlar": "necha marta ko'rilgani",
    "bot": "bot havolasi (@username)",
    "tavsif": "erkin tavsif (eski kinolarda)",
}

TEMPLATE_KEY = "caption_template"
ANNOUNCE_KEY = "announce_channel"  # yangi kino e'lon qilinadigan kanal (chat_id)

# Kanalga yuboriladigan e'lon: rasm tagida chiqadi.
# Qiymati bo'sh qator (masalan kategoriya) avtomatik tushib qoladi.
ANNOUNCE_TEMPLATE = (
    "{e_yangi} <b>Yangi kino yuklandi!</b>\n"
    f"{SEPARATOR}\n"
    "{e_film} Nomi: <b>{nom}</b>\n"
    "{e_janr} Janri: <b>{janr}</b>\n"
    "{e_til} Tili: <b>{til}</b>\n"
    "{e_sifat} Sifati: <b>{sifat}</b>\n"
    "{e_kat} Kategoriya: <b>{kategoriya}</b>\n"
    f"{SEPARATOR}\n"
    "{e_kod} Kod: <code>{kod}</code>\n"
    "{e_bot} {bot}"
)
CAPTION_LIMIT = 1024

# ---------- premium emoji ----------
# Har bir belgi: oddiy emoji (zaxira) + admin panelda biriktiriladigan premium emoji ID'si.
EMOJI_DEFAULTS = {
    "film": "🍿",
    "til": "🇺🇿",
    "sifat": "💾",
    "janr": "🎞",
    "kat": "⛔️",
    "kod": "🗂",
    "kor": "👁",
    "bot": "🤖",
    "yangi": "🆕",
}
EMOJI_TITLES = {
    "film": "Kino nomi",
    "til": "Til",
    "sifat": "Sifat",
    "janr": "Janr",
    "kat": "Kategoriya",
    "kod": "Kod",
    "kor": "Ko'rishlar",
    "bot": "Bot",
    "yangi": "Yangi kino",
}
EMOJI_PLACEHOLDERS = {f"e_{key}": f"{title} belgisi" for key, title in EMOJI_TITLES.items()}
EMOJI_KEY = "emoji_ids"
STICKER_KEY = "welcome_sticker"
EMOJI_IDS: dict[str, str] = {}  # {"film": "5368324170671202286"}


def set_emoji_ids(raw: str) -> None:
    """Bazadagi JSON'dan premium emoji ID'larini yuklaydi (bo'sh qiymat — hammasi oddiy)."""
    EMOJI_IDS.clear()
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {}
    for key, value in data.items():
        if key in EMOJI_DEFAULTS and str(value).isdigit():
            EMOJI_IDS[key] = str(value)


def emoji_html(name: str) -> str:
    """Premium emoji ID'si bo'lsa <tg-emoji>, bo'lmasa oddiy emoji."""
    fallback = EMOJI_DEFAULTS[name]
    emoji_id = EMOJI_IDS.get(name)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback


# Bot ishga tushganda to'ldiriladi
BOT_USERNAME = ""
TEMPLATE = DEFAULT_TEMPLATE


def set_bot_username(username: str) -> None:
    global BOT_USERNAME
    BOT_USERNAME = username or ""


def set_template(template: str) -> None:
    """Bo'sh qiymat berilsa — standart shablonga qaytadi."""
    global TEMPLATE
    TEMPLATE = template.strip() or DEFAULT_TEMPLATE


def number(value: int) -> str:
    """1245 -> «1 245»"""
    return f"{value:,}".replace(",", " ")


def esc(text) -> str:
    """HTML uchun xavfsiz matn. Apostrof (O'zbek) o'zgarishsiz qoladi."""
    return html.escape(str(text), quote=False)


def field(movie, name: str) -> str:
    """Ustun bazada bo'lmasa ham (eski yozuvlar) xatolik bermaydi."""
    try:
        return movie[name] or ""
    except (IndexError, KeyError):
        return ""


COLUMNS = {
    "nom": "title",
    "til": "language",
    "sifat": "quality",
    "janr": "genre",
    "kategoriya": "category",
    "kod": "code",
    "tavsif": "caption",
}

PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def template_values(movie, views: int | None = None) -> dict[str, str]:
    values = {key: esc(field(movie, column)) for key, column in COLUMNS.items()}
    values["korishlar"] = number(movie["views"] if views is None else views)
    values["bot"] = f"@{BOT_USERNAME}" if BOT_USERNAME else ""
    for key in EMOJI_DEFAULTS:
        values[f"e_{key}"] = emoji_html(key)
    return values


def render_template(template: str, values: dict[str, str]) -> str:
    """Qiymati bo'sh o'rin egallovchi bo'lgan qator butunlay tushib qoladi."""
    lines: list[str] = []
    for line in template.split("\n"):
        used = [name for name in PLACEHOLDER_RE.findall(line) if name in values]
        if used and not all(values[name] for name in used):
            continue
        rendered = PLACEHOLDER_RE.sub(
            lambda match: values.get(match.group(1), match.group(0)), line
        )
        # Ketma-ket takrorlangan ajratgichlarni yig'ishtiramiz
        if lines and rendered.strip() and rendered == lines[-1]:
            continue
        lines.append(rendered)
    return "\n".join(lines).strip()


def movie_caption(movie, views: int | None = None) -> str:
    """Foydalanuvchiga yuboriladigan caption — joriy shablon bo'yicha."""
    return render_template(TEMPLATE, template_values(movie, views))


def announce_caption(movie) -> str:
    """Kanal e'loni uchun caption."""
    return render_template(ANNOUNCE_TEMPLATE, template_values(movie, views=0))


# Shablonni ko'rib chiqish uchun namuna
SAMPLE_MOVIE = {
    "title": "Buni ishq deydilar 2",
    "language": "O'zbek tilida",
    "quality": "720p",
    "genre": "Romantic komediya",
    "category": "16+",
    "code": "1320",
    "caption": "",
    "views": 1245,
}


def template_preview(template: str) -> str:
    return render_template(template, template_values(SAMPLE_MOVIE))


def movie_info(movie) -> str:
    """Admin panelidagi batafsil ma'lumot."""
    dash = lambda name: esc(field(movie, name)) or "—"
    return (
        f"🎬 <b>{esc(field(movie, 'title')) or 'Nomsiz'}</b>\n\n"
        f"🗂 Kod: <code>{esc(movie['code'])}</code>\n"
        f"🇺🇿 Tili: {dash('language')}\n"
        f"💾 Sifati: {dash('quality')}\n"
        f"🎞️ Janri: {dash('genre')}\n"
        f"⛔️ Kategoriya: {dash('category')}\n"
        f"📦 Turi: {movie['file_type']}\n"
        f"👁 Ko'rishlar: {movie['views']}\n"
        f"🗓 Qo'shilgan: {movie['created_at']}"
    )
