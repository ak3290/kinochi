from __future__ import annotations

from typing import Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import is_admin

PAGE_SIZE = 8

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Agar bu Inline tugma bo'lsa:
admin_panel_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kinolar boshqaruvi", callback_data="manage_movies")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")]
    ]
)

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Admin panel tugmasi
admin_panel_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Admin panel", callback_data="admin_panel")]
    ]
)

# Kanal tanlash tugmasi uchun identifikator (javobda ham shu qaytadi)
CHANNEL_REQUEST_ID = 1
ANNOUNCE_REQUEST_ID = 2

# ---------- reply klaviaturalar ----------

BTN_ADMIN = "🛠 Admin panel"
BTN_ADD_MOVIE = "➕ Kino qo'shish"
BTN_MOVIES = "🎬 Kinolar"
BTN_STATS = "📊 Statistika"
BTN_CHANNELS = "📢 Majburiy obuna"
BTN_TEMPLATE = "🧩 Shablon"
BTN_ANNOUNCE = "📣 E'lon kanali"
BTN_EMOJI = "✨ Premium emoji"
BTN_BACK = "◀️ Bosh menyu"
BTN_CANCEL = "❌ Bekor qilish"
BTN_SELECT_CHANNEL = "📢 Kanalni tanlash"
BTN_SKIP = "⏭ O'tkazib yuborish"

# Menyu tugmalari — FSM holatidagi handlerlar ularni ushlab qolmasligi uchun
MENU_BUTTONS = frozenset(
    {
        BTN_ADMIN,
        BTN_ADD_MOVIE,
        BTN_MOVIES,
        BTN_STATS,
        BTN_CHANNELS,
        BTN_TEMPLATE,
        BTN_ANNOUNCE,
        BTN_EMOJI,
        BTN_BACK,
        BTN_CANCEL,
        BTN_SKIP,
        BTN_SELECT_CHANNEL,
    }
)


def main_menu(user_id: int) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """Oddiy foydalanuvchida klaviatura yo'q, adminda — admin tugmasi."""
    if not is_admin(user_id):
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_ADMIN)]],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADD_MOVIE), KeyboardButton(text=BTN_MOVIES)],
            [KeyboardButton(text=BTN_STATS), KeyboardButton(text=BTN_CHANNELS)],
            [KeyboardButton(text=BTN_TEMPLATE), KeyboardButton(text=BTN_ANNOUNCE)],
            [KeyboardButton(text=BTN_EMOJI), KeyboardButton(text=BTN_BACK)],
        ],
        resize_keyboard=True,
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


def step_menu(options: Sequence[str] = (), skip: bool = True) -> ReplyKeyboardMarkup:
    """Bosqichli so'rovlar uchun: tayyor variantlar + o'tkazib yuborish/bekor qilish."""
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text=option) for option in options[i : i + 2]]
        for i in range(0, len(options), 2)
    ]
    last = [KeyboardButton(text=BTN_CANCEL)]
    if skip:
        last.insert(0, KeyboardButton(text=BTN_SKIP))
    rows.append(last)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def select_channel_menu(request_id: int = CHANNEL_REQUEST_ID) -> ReplyKeyboardMarkup:
    """Tugma bosilganda Telegram kanal tanlash oynasini ochadi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=BTN_SELECT_CHANNEL,
                    request_chat=KeyboardButtonRequestChat(
                        request_id=request_id,
                        chat_is_channel=True,
                        bot_is_member=True,
                        request_title=True,
                        request_username=True,
                    ),
                )
            ],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


# ---------- inline klaviaturalar ----------


def announce_kb(is_set: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📢 Kanalni tanlash", callback_data="ann_set")]]
    if is_set:
        rows.append([InlineKeyboardButton(text="🗑 O'chirish", callback_data="ann_off")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def emoji_kb(
    items: Sequence[tuple[str, str]], has_custom: bool, has_sticker: bool
) -> InlineKeyboardMarkup:
    """items — [(kalit, tugma matni)]."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text=label, callback_data=f"emo:{key}")
            for key, label in items[i : i + 2]
        ]
        for i in range(0, len(items), 2)
    ]
    if has_custom:
        rows.append([InlineKeyboardButton(text="♻️ Oddiy emojiga qaytarish", callback_data="emo_reset")])
    rows.append([InlineKeyboardButton(text="🎭 Start stikerini o'rnatish", callback_data="stk_set")])
    if has_sticker:
        rows.append([InlineKeyboardButton(text="🗑 Start stikerini o'chirish", callback_data="stk_off")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def watch_kb(url: str) -> InlineKeyboardMarkup:
    """Kanal postidagi «Kinoni ko'rish» tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎬 Kinoni ko'rish", url=url)]]
    )


def subscribe_kb(channels: Sequence) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, channel in enumerate(channels, start=1):
        url = channel["invite_link"]
        if channel["username"]:
            url = f"https://t.me/{channel['username']}"
        if not url:
            continue
        rows.append(
            [InlineKeyboardButton(text=f"📢 {channel['title'] or f'Kanal {index}'}", url=url)]
        )
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def movies_list_kb(movies: Sequence, page: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"🎬 {movie['code']} — {movie['title'][:30] or 'nomsiz'}",
                callback_data=f"movie:{movie['id']}:{page}",
            )
        ]
        for movie in movies
    ]

    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        if pages > 3:
            nav.append(InlineKeyboardButton(text="⏮", callback_data="page:0"))
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"page:{page + 1}"))
        if pages > 3:
            nav.append(InlineKeyboardButton(text="⏭", callback_data=f"page:{pages - 1}"))
    rows.append(nav)
    rows.append(
        [InlineKeyboardButton(text="🔎 Kod yoki nom bo'yicha topish", callback_data="find")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def found_movies_kb(movies: Sequence) -> InlineKeyboardMarkup:
    """Admin qidiruvi natijalari — bosilganda boshqaruv kartochkasi ochiladi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🎬 {movie['code']} — {movie['title'][:30] or 'nomsiz'}",
                    callback_data=f"movie:{movie['id']}:0",
                )
            ]
            for movie in movies
        ]
    )


def movie_manage_kb(movie_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Tahrirlash", callback_data=f"edit:{movie_id}:{page}"
                ),
                InlineKeyboardButton(
                    text="🗑 O'chirish", callback_data=f"del:{movie_id}:{page}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📣 Kanalga e'lon qilish", callback_data=f"annsend:{movie_id}:{page}"
                )
            ],
            [InlineKeyboardButton(text="◀️ Ro'yxat", callback_data=f"page:{page}")],
        ]
    )


def edit_movie_kb(movie_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗂 Kod", callback_data=f"field:code:{movie_id}:{page}"
                ),
                InlineKeyboardButton(
                    text="🍿 Nom", callback_data=f"field:title:{movie_id}:{page}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🇺🇿 Til", callback_data=f"field:language:{movie_id}:{page}"
                ),
                InlineKeyboardButton(
                    text="💾 Sifat", callback_data=f"field:quality:{movie_id}:{page}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎞️ Janr", callback_data=f"field:genre:{movie_id}:{page}"
                ),
                InlineKeyboardButton(
                    text="⛔️ Kategoriya", callback_data=f"field:category:{movie_id}:{page}"
                ),
            ],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"movie:{movie_id}:{page}")],
        ]
    )


def confirm_delete_kb(movie_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, o'chirilsin", callback_data=f"delyes:{movie_id}:{page}"
                ),
                InlineKeyboardButton(
                    text="❌ Yo'q", callback_data=f"movie:{movie_id}:{page}"
                ),
            ]
        ]
    )


def template_kb(is_custom: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="✏️ O'zgartirish", callback_data="tpl_edit")]]
    if is_custom:
        rows.append(
            [InlineKeyboardButton(text="♻️ Standart shablon", callback_data="tpl_reset")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channels_kb(channels: Sequence) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=f"🗑 {channel['title'] or channel['chat_id']}",
                callback_data=f"chdel:{channel['chat_id']}",
            )
        ]
        for channel in channels
    ]
    rows.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="chadd")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
