"""Botning asosiy oqimlarini soxta (mock) Telegram sessiyasi orqali tekshiradi.

Ishga tushirish:  python tests/test_flow.py
"""
import asyncio, os, sys, tempfile
from datetime import datetime, timezone

os.environ["BOT_TOKEN"] = "123456:TEST"
os.environ["ADMINS"] = "111"
DBF = tempfile.mktemp(suffix=".db")
os.environ["DB_PATH"] = DBF
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ChatMemberAdministrator, ChatMemberLeft, ChatMemberMember, Message as TgMessage, Update, User

from database import db
from handlers import get_routers
from middlewares import SubscriptionMiddleware

NOW = int(datetime.now(tz=timezone.utc).timestamp())
SUBSCRIBED = {"status": "member"}
CHAT_FAIL = False
HTML_FAIL = False
ANN_FAIL = False

class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
    async def close(self): pass
    async def stream_content(self, *a, **kw):
        yield b""
    async def make_request(self, bot, method, timeout=None):
        name = type(method).__name__
        self.calls.append((name, method))
        chat_id = getattr(method, "chat_id", 1)
        # Faqat namuna (preview) xabari rad etiladi — xato haqidagi xabar emas
        if name == "SendMessage" and HTML_FAIL and "Buni ishq" in (getattr(method, "text", "") or ""):
            from aiogram.exceptions import TelegramBadRequest
            raise TelegramBadRequest(method=method, message="Bad Request: can't parse entities")
        if name in {"SendPhoto", "SendMessage"} and ANN_FAIL and chat_id == -1001:
            from aiogram.exceptions import TelegramForbiddenError
            raise TelegramForbiddenError(method=method, message="Forbidden: bot is not a member of the channel chat")
        if name in {"SendMessage", "SendVideo", "SendDocument", "SendPhoto", "SendSticker", "EditMessageText"}:
            payload = {"message_id": 999, "date": NOW, "chat": {"id": chat_id, "type": "private"}}
            txt = getattr(method, "text", None)
            if txt: payload["text"] = txt
            return TgMessage.model_validate(payload, context={"bot": bot})
        if name == "GetChatMember":
            u = method.user_id
            usr = User(id=u, is_bot=False, first_name="U")
            if u == bot.id:
                return ChatMemberAdministrator(user=usr, can_be_edited=False, is_anonymous=False,
                    can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=True,
                    can_restrict_members=True, can_promote_members=True, can_change_info=True,
                    can_invite_users=True, can_post_stories=True, can_edit_stories=True,
                    can_delete_stories=True)
            if SUBSCRIBED["status"] == "member":
                return ChatMemberMember(user=usr)
            return ChatMemberLeft(user=usr)
        if name == "GetChat" and CHAT_FAIL:
            from aiogram.exceptions import TelegramBadRequest
            raise TelegramBadRequest(method=method, message="Bad Request: chat not found")
        if name == "GetChat":
            return method.__returning__.model_validate(
                {"id": -1001, "type": "channel", "title": "Test kanal", "username": "testkanal",
                 "accent_color_id": 0, "max_reaction_count": 11, "accepted_gift_types": {"unlimited_gifts": False, "limited_gifts": False, "unique_gifts": False, "premium_subscription": False, "gifts_from_channels": False}}, context={"bot": bot})
        if name == "GetMe":
            return method.__returning__.model_validate({"id": 7, "is_bot": True, "first_name": "Kinochi", "username": "kinochi_bot"}, context={"bot": bot})
        return True
    def last(self, n=1):
        return [c for c in self.calls][-n:]

session = FakeSession()
bot = Bot(token="123456:TEST", session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.message.outer_middleware(SubscriptionMiddleware())
dp.callback_query.outer_middleware(SubscriptionMiddleware())
dp.include_routers(*get_routers())

uid = 0
def msg(user_id, text=None, video=False, caption=None, photo=False, entities=None, sticker=False):
    global uid; uid += 1
    m = {"message_id": uid, "date": NOW, "chat": {"id": user_id, "type": "private"},
         "from": {"id": user_id, "is_bot": False, "first_name": "Ali", "username": "ali"}}
    if text is not None: m["text"] = text
    if entities: m["entities"] = entities
    if sticker:
        m["sticker"] = {"file_id": "STK1", "file_unique_id": "s1", "type": "regular",
                        "width": 512, "height": 512, "is_animated": False, "is_video": False}
    if photo:
        m["photo"] = [{"file_id": "PHOTO123", "file_unique_id": "p1", "width": 100, "height": 100}]
    if video:
        m["video"] = {"file_id": "VID123", "file_unique_id": "u1", "width": 100, "height": 100, "duration": 60}
        m["caption"] = caption
    return {"update_id": uid, "message": m}

def shared(user_id, chat_id=-1001):
    global uid; uid += 1
    return {"update_id": uid, "message": {"message_id": uid, "date": NOW,
        "chat": {"id": user_id, "type": "private"},
        "from": {"id": user_id, "is_bot": False, "first_name": "Ali"},
        "chat_shared": {"request_id": 1, "chat_id": chat_id,
                        "title": "Test kanal", "username": "testkanal"}}}

def announce_shared(user_id, chat_id=-1001):
    p = shared(user_id, chat_id)
    p["message"]["chat_shared"]["request_id"] = 2
    return p

def cb(user_id, data):
    global uid; uid += 1
    return {"update_id": uid, "callback_query": {"id": str(uid), "chat_instance": "ci",
        "from": {"id": user_id, "is_bot": False, "first_name": "Ali"}, "data": data,
        "message": {"message_id": 500, "date": NOW, "chat": {"id": user_id, "type": "private"}, "text": "x"}}}

async def feed(payload):
    session.calls.clear()
    await dp.feed_update(bot, Update.model_validate(payload, context={"bot": bot}))
    return session.calls

def find(calls, name):
    for n, m in calls:
        if n == name:
            return m
    raise AssertionError(f"{name} chaqirilmadi: {[n for n, _ in calls]}")

def texts(calls):
    return " || ".join(str(getattr(d, "text", None) or getattr(d, "caption", None) or "") for _, d in calls)

async def main():
    await db.connect()
    from utils import set_bot_username
    set_bot_username("kinochi_bot")  # bot.py da get_me() dan keyin shunday o'rnatiladi
    ADMIN, USER = 111, 222

    c = await feed(msg(ADMIN, "/start"))
    assert "xush kelibsiz" in texts(c), texts(c)
    datas = [b.callback_data for row in find(c, "SendMessage").reply_markup.inline_keyboard for b in row]
    assert "adm:home" in datas and "u:new:0" in datas, datas
    print("1. /start admin -> inline menyu + «Admin panel» tugmasi ✔")

    c = await feed(msg(USER, "/start"))
    datas = [b.callback_data for row in find(c, "SendMessage").reply_markup.inline_keyboard for b in row]
    assert "u:new:0" in datas and "adm:home" not in datas, datas
    print("2. /start oddiy user -> inline menyu (admin tugmasisiz) ✔")

    c = await feed(msg(ADMIN, "🛠 Admin panel"))
    assert "Admin panel" in texts(c)
    print("3. Admin panel ochildi ✔")

    await feed(msg(ADMIN, "➕ Kino qo'shish"))
    c = await feed(msg(ADMIN, video=True))
    assert "Kino nomini" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "Buni ishq deydilar 2"))
    assert "Tilini" in texts(c), texts(c)
    assert [b.text for b in find(c, "SendMessage").reply_markup.keyboard[0]][0] == "O'zbek tilida"
    c = await feed(msg(ADMIN, "O'zbek tilida"))
    assert "Sifatini" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "720p"))
    assert "Janrini" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "Romantic komediya"))
    assert "kategoriyasini" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "⏭ O'tkazib yuborish"))
    assert "posterini" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "matn"))   # rasm o'rniga matn — rad etilishi kerak
    assert "rasm yuboring" in texts(c), texts(c)
    c = await feed(msg(ADMIN, photo=True))
    assert "kodini" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "1320"))
    assert "saqlandi" in texts(c), texts(c)

    m = await db.get_movie_by_code("1320")
    assert m["title"] == "Buni ishq deydilar 2" and m["file_id"] == "VID123"
    assert m["language"] == "O'zbek tilida" and m["quality"] == "720p"
    assert m["genre"] == "Romantic komediya" and m["category"] == ""
    assert m["poster_id"] == "PHOTO123"
    assert m["views"] == 0, "admin ko'rgan preview statistikani buzmasligi kerak"
    print("4. Kino qo'shish — har bir maydon alohida so'raldi ✔")

    from utils import movie_caption
    cap = movie_caption(m, views=1)
    expected = ("🍿 <b>Buni ishq deydilar 2</b>\n"
                "➖➖➖➖➖➖➖➖➖➖➖➖\n"
                "🇺🇿 Tili: <b>O'zbek tilida</b>\n"
                "💾 Sifati: <b>720p</b>\n"
                "🎞 Janri: <b>Romantic komediya</b>\n"
                "➖➖➖➖➖➖➖➖➖➖➖➖\n"
                "🗂 Kod: <code>1320</code>\n"
                "👁 Ko'rildi: 1 marta\n"
                "🤖 @kinochi_bot")
    assert cap == expected, repr(cap)
    assert "Kategoriya" not in cap, "bo'sh maydon chiqmasligi kerak"
    assert find(c, "SendVideo").caption == movie_caption(m, views=0)
    print("5. Caption: bo'sh maydon yashirildi, kod nusxalanadi, bot havolasi bor ✔")

    await feed(msg(ADMIN, "➕ Kino qo'shish"))
    await feed(msg(ADMIN, video=True))
    c = await feed(msg(ADMIN, "⏭ O'tkazib yuborish"))
    assert "majburiy" in texts(c), texts(c)
    await feed(msg(ADMIN, "Boshqa kino"))
    await feed(msg(ADMIN, "⏭ O'tkazib yuborish"))
    await feed(msg(ADMIN, "⏭ O'tkazib yuborish"))
    await feed(msg(ADMIN, "⏭ O'tkazib yuborish"))
    await feed(msg(ADMIN, "⏭ O'tkazib yuborish"))
    await feed(msg(ADMIN, "⏭ O'tkazib yuborish"))   # poster
    c = await feed(msg(ADMIN, "1320"))
    assert "band" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "❌ Bekor qilish"))
    assert "Bekor" in texts(c)
    assert await db.count_movies() == 1
    print("6. Nom majburiy, qolganlari o'tkaziladi, takroriy kod rad etildi ✔")

    c = await feed(msg(USER, "1320"))
    assert c[0][0] == "SendVideo" and "<code>1320</code>" in texts(c)
    assert "👁 Ko'rildi: 1 marta" in texts(c), "ko'rishlar darhol yangilanishi kerak"
    assert (await db.get_movie_by_code("1320"))["views"] == 1
    print("7. User kod bo'yicha topdi, views +1 ✔")

    c = await feed(msg(USER, "ishq"))
    assert c[0][0] == "SendVideo"
    c = await feed(msg(USER, "komediya"))
    assert c[0][0] == "SendVideo", "janr bo'yicha ham topilishi kerak"
    print("8. Nom va janr bo'yicha qidiruv ✔")

    c = await feed(msg(USER, "yo'q kino"))
    assert "topilmadi" in texts(c)
    print("9. Topilmadi xabari ✔")

    c = await feed(msg(ADMIN, "📊 Statistika"))
    t = texts(c)
    assert "Foydalanuvchilar" in t and "Buni ishq deydilar 2" in t
    print("10. Statistika ✔")

    c = await feed(msg(ADMIN, "🎬 Kinolar"))
    kb = c[0][1].reply_markup.inline_keyboard
    assert "1320" in kb[0][0].text
    c = await feed(cb(ADMIN, kb[0][0].callback_data))
    assert "Buni ishq deydilar 2" in texts(c) and "720p" in texts(c)
    c = await feed(cb(ADMIN, f"edit:{m['id']}:0"))
    c = await feed(cb(ADMIN, f"field:quality:{m['id']}:0"))
    assert [b.text for b in find(c, "SendMessage").reply_markup.keyboard[0]] == ["480p", "720p"]
    c = await feed(msg(ADMIN, "1080p"))
    assert "Yangilandi" in texts(c)
    assert (await db.get_movie(m["id"]))["quality"] == "1080p"
    print("11. Ro'yxat + tahrirlash ✔")

    c = await feed(cb(ADMIN, f"del:{m['id']}:0"))
    assert "o'chirilsinmi" in texts(c)
    c = await feed(cb(ADMIN, f"delyes:{m['id']}:0"))
    assert await db.count_movies() == 0
    print("12. O'chirish (tasdiq bilan) ✔")

    c = await feed(msg(ADMIN, "📢 Majburiy obuna"))
    assert "kanal qo'shilmagan" in texts(c)
    c = await feed(cb(ADMIN, "chadd"))
    btn = find(c, "SendMessage").reply_markup.keyboard[0][0]
    assert btn.text == "📢 Kanalni tanlash"
    assert btn.request_chat.chat_is_channel and btn.request_chat.bot_is_member
    print("13. «Kanalni tanlash» tugmasi chiqdi ✔")

    c = await feed(shared(ADMIN))
    assert "majburiy obunaga qo'shildi" in texts(c), texts(c)
    assert await db.count_channels() == 1
    print("14. Tugma orqali tanlangan kanal qo'shildi ✔")

    await db.delete_channel(-1001)
    await feed(cb(ADMIN, "chadd"))
    c = await feed(msg(ADMIN, "@testkanal"))
    assert "majburiy obunaga qo'shildi" in texts(c), texts(c)
    assert await db.count_channels() == 1
    print("15. Qo'lda (@username) qo'shish ham ishlaydi ✔")

    global SUBSCRIBED
    SUBSCRIBED = {"status": "left"}
    c = await feed(msg(USER, "1320"))
    assert "obuna bo'ling" in texts(c), texts(c)
    kb = find(c, "SendMessage").reply_markup.inline_keyboard
    assert kb[0][0].url == "https://t.me/testkanal"
    c = await feed(cb(USER, "check_subs"))
    ans = find(c, "AnswerCallbackQuery")
    assert ans.show_alert and "obuna bo'lmadingiz" in ans.text
    print("16. Majburiy obuna bloklaydi ✔")

    c = await feed(msg(ADMIN, "1320"))
    assert not any(n == "GetChatMember" for n, _ in c) and "obuna bo'ling" not in texts(c)
    print("17. Admin obunadan ozod ✔")

    SUBSCRIBED = {"status": "member"}
    c = await feed(cb(USER, "check_subs"))
    assert "Rahmat" in find(c, "AnswerCallbackQuery").text
    assert "xush kelibsiz" in texts(c)
    print("18. Obuna tekshiruvi o'tdi ✔")

    c = await feed(cb(ADMIN, "chdel:-1001"))
    assert await db.count_channels() == 0
    print("19. Kanal o'chirildi ✔")

    global CHAT_FAIL
    CHAT_FAIL = True
    await feed(cb(ADMIN, "chadd"))
    c = await feed(shared(ADMIN, -1009))
    t = texts(c)
    assert "«Test kanal» kanaliga bot kira olmadi" in t, t
    assert "chat not found" in t and "@kinochi_bot" in t, t
    assert await db.count_channels() == 0
    CHAT_FAIL = False
    print("20. Bot kanalda yo'q -> aniq xato + yo'riqnoma ✔")

    c = await feed(msg(ADMIN, "🧩 Shablon"))
    t = texts(c)
    assert "standart" in t and "{nom}" in t and "Buni ishq deydilar 2" in t, t
    assert find(c, "SendMessage").reply_markup.inline_keyboard[0][0].callback_data == "tpl_edit"
    print("21. Shablon bo'limi: joriy shablon + namuna ko'rsatildi ✔")

    await feed(cb(ADMIN, "tpl_edit"))
    c = await feed(msg(ADMIN, "🍿 {nom}\n🗂 {kod}\n🌐 {noma_lum}"))
    assert "Noma'lum o'rin egallovchi" in texts(c) and "noma_lum" in texts(c), texts(c)
    assert await db.get_setting("caption_template") == "", "xato shablon saqlanmasligi kerak"
    print("22. Noma'lum o'rin egallovchi rad etildi ✔")

    global HTML_FAIL
    HTML_FAIL = True
    c = await feed(msg(ADMIN, "<b>{nom}\n{kod}"))
    assert "HTML teglarida xato" in texts(c), texts(c)
    assert await db.get_setting("caption_template") == "", "xato shablon saqlanmasligi kerak"
    HTML_FAIL = False
    print("23. Buzuq HTML Telegram tomonidan rad etildi, saqlanmadi ✔")

    c = await feed(msg(ADMIN, "🎬 <b>{nom}</b> ({sifat})\n🎭 {janr}\n🗂 Kod: {kod}"))
    assert "Shablon saqlandi" in texts(c), texts(c)
    assert (await db.get_setting("caption_template")).startswith("🎬 <b>{nom}</b>")

    # 12-qadamda kino o'chirilgan edi — shablonni sinash uchun yangisini qo'shamiz
    await db.add_movie(
        "1320", "Buni ishq deydilar 2", "VID123", "video",
        language="O'zbek tilida", quality="1080p", genre="", category="16+",
    )
    c = await feed(msg(USER, "1320"))
    cap = find(c, "SendVideo").caption
    assert cap == "🎬 <b>Buni ishq deydilar 2</b> (1080p)\n🗂 Kod: 1320", repr(cap)
    print("24. Yangi shablon saqlandi va kinoga darhol qo'llanildi ✔")
    print("    (janr o'chirilgani uchun {janr} qatori tushib qoldi)")

    c = await feed(msg(ADMIN, "🧩 Shablon"))
    assert "o‘zgartirilgan" in texts(c), texts(c)
    kb = find(c, "SendMessage").reply_markup.inline_keyboard
    assert kb[1][0].callback_data == "tpl_reset"
    c = await feed(cb(ADMIN, "tpl_reset"))
    assert await db.get_setting("caption_template") == ""
    c = await feed(msg(USER, "1320"))
    assert "👁 Ko'rildi:" in find(c, "SendVideo").caption, "standart shablon qaytishi kerak"
    print("25. Standart shablonga qaytarildi ✔")

    # 1000+ kino uchun: kod/nom bo'yicha chaqirib tahrirlash va o'chirish
    for i in range(1, 13):
        await db.add_movie(f"90{i}", f"Test kino {i}", "F", "video", quality="720p")
    await db.add_movie("555", "Qora tuman", "F", "video", genre="Triller")

    c = await feed(msg(ADMIN, "🎬 Kinolar"))
    t = texts(c)
    assert "jami: 14" in t and "kodini" in t, t
    kb = find(c, "SendMessage").reply_markup.inline_keyboard
    assert [b.text for b in kb[-3]] == ["1/2", "➡️"], [b.text for b in kb[-3]]
    assert kb[-2][0].callback_data == "find" and kb[-1][0].callback_data == "adm:home"
    print("26. Ro'yxat: sahifalash + «kod bo'yicha topish» tugmasi ✔")

    c = await feed(msg(ADMIN, "555"))
    t = texts(c)
    assert "Qora tuman" in t and "Triller" in t, t
    kb = find(c, "SendMessage").reply_markup.inline_keyboard
    assert kb[0][0].callback_data.startswith("edit:") and kb[0][1].callback_data.startswith("del:")
    print("27. Kod yozildi -> kartochka + tahrirlash/o'chirish tugmalari ✔")

    await feed(msg(ADMIN, "🎬 Kinolar"))
    c = await feed(msg(ADMIN, "Test kino"))
    t = texts(c)
    assert "12 ta natija" in t, t
    kb = find(c, "SendMessage").reply_markup.inline_keyboard
    assert len(kb) == 12 and kb[0][0].callback_data.startswith("movie:")
    c = await feed(cb(ADMIN, kb[0][0].callback_data))
    assert "Test kino" in texts(c)
    print("28. Nom bo'yicha ro'yxat -> kartochka ✔")

    await feed(msg(ADMIN, "🎬 Kinolar"))
    c = await feed(msg(ADMIN, "yoq-bunday-kino"))
    assert "topilmadi" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "555"))          # holat saqlangan — darhol topadi
    assert "Qora tuman" in texts(c)
    print("29. Topilmadi -> holat saqlanadi, keyingi kod ishlaydi ✔")

    await feed(msg(ADMIN, "🎬 Kinolar"))
    c = await feed(msg(ADMIN, "📊 Statistika"))
    assert "Foydalanuvchilar" in texts(c), "menyu tugmasi qidiruv sifatida qabul qilinmasligi kerak"
    print("30. Qidiruv holatida menyu tugmalari ishlayveradi ✔")

    await feed(msg(ADMIN, "🎬 Kinolar"))
    c = await feed(msg(ADMIN, "901"))
    movie_id = find(c, "SendMessage").reply_markup.inline_keyboard[0][1].callback_data.split(":")[1]
    await feed(cb(ADMIN, f"del:{movie_id}:0"))
    c = await feed(cb(ADMIN, f"delyes:{movie_id}:0"))
    assert await db.get_movie_by_code("901") is None
    assert await db.count_movies() == 13
    print("31. Kod orqali topib o'chirildi ✔")

    # ---------- kanalga e'lon ----------
    global ANN_FAIL
    c = await feed(msg(ADMIN, "📣 E'lon kanali"))
    assert "tanlanmagan" in texts(c), texts(c)
    c = await feed(cb(ADMIN, "ann_set"))
    btn = find(c, "SendMessage").reply_markup.keyboard[0][0]
    assert btn.request_chat.request_id == 2
    c = await feed(announce_shared(ADMIN, -1002))
    assert "E'lon kanali" in texts(c) and await db.get_setting("announce_channel") == "-1001", texts(c)
    print("32. E'lon kanali tanlandi va saqlandi ✔")

    async def add_via_bot(code, poster):
        await feed(msg(ADMIN, "➕ Kino qo'shish"))
        await feed(msg(ADMIN, video=True))
        await feed(msg(ADMIN, "Yangi film"))
        await feed(msg(ADMIN, "O'zbek tilida"))
        await feed(msg(ADMIN, "1080p"))
        await feed(msg(ADMIN, "Drama"))
        await feed(msg(ADMIN, "16+"))
        if poster:
            await feed(msg(ADMIN, photo=True))
        else:
            await feed(msg(ADMIN, "⏭ O'tkazib yuborish"))
        return await feed(msg(ADMIN, code))

    c = await add_via_bot("7001", poster=True)
    photo = find(c, "SendPhoto")
    assert photo.chat_id == -1001 and photo.photo == "PHOTO123"
    assert photo.caption.startswith("🆕 <b>Yangi kino yuklandi!</b>"), photo.caption
    for part in ("Yangi film", "Drama", "O'zbek tilida", "1080p", "16+", "<code>7001</code>"):
        assert part in photo.caption, (part, photo.caption)
    new_id = (await db.get_movie_by_code("7001"))["id"]
    assert photo.reply_markup.inline_keyboard[0][0].url == f"https://t.me/kinochi_bot?start=m{new_id}"
    assert "kanalga yuborildi" in texts(c)
    print("33. Yangi kino -> kanalga rasm + janr/til/sifat bilan e'lon ketdi ✔")

    c = await add_via_bot("7002", poster=False)
    assert any(n == "SendMessage" and getattr(m, "chat_id", None) == -1001 for n, m in c)
    assert not any(n == "SendPhoto" and getattr(m, "chat_id", None) == -1001 for n, m in c)
    print("34. Poster yo'q bo'lsa e'lon matn ko'rinishida ketdi ✔")

    ANN_FAIL = True
    c = await add_via_bot("7003", poster=True)
    assert await db.get_movie_by_code("7003") is not None
    assert "e'lon yuborilmadi" in texts(c), texts(c)
    ANN_FAIL = False
    print("35. Kanalga yuborib bo'lmasa kino baribir saqlanadi, admin ogohlantiriladi ✔")

    c = await feed(msg(USER, f"/start m{new_id}"))
    assert any(n == "SendVideo" for n, _ in c), [n for n, _ in c]
    c = await feed(msg(USER, "/start m99999"))
    assert "topilmadi" in texts(c)
    print("36. Kanal tugmasi (/start m<id>) kinoni ochadi ✔")

    c = await feed(cb(ADMIN, "ann_off"))
    assert await db.get_setting("announce_channel") == ""
    c = await add_via_bot("7004", poster=True)
    assert not any(n == "SendPhoto" and getattr(m, "chat_id", None) == -1001 for n, m in c)
    print("37. E'lon kanali o'chirilsa e'lon yuborilmaydi ✔")

    # ---------- premium emoji, stiker, qayta e'lon ----------
    from utils import EMOJI_IDS
    c = await feed(msg(ADMIN, "✨ Premium emoji"))
    assert "Premium emoji" in texts(c), texts(c)
    c = await feed(cb(ADMIN, "emo:film"))
    c = await feed(msg(ADMIN, "oddiy matn"))
    assert "premium emoji emas" in texts(c), texts(c)
    ent = [{"type": "custom_emoji", "offset": 0, "length": 2, "custom_emoji_id": "5368324170671202286"}]
    c = await feed(msg(ADMIN, "🍿", entities=ent))
    assert "saqlandi" in texts(c), texts(c)
    assert EMOJI_IDS == {"film": "5368324170671202286"}
    assert "film" in await db.get_setting("emoji_ids")
    c = await feed(msg(USER, "1320"))
    cap = find(c, "SendVideo").caption
    assert '<tg-emoji emoji-id="5368324170671202286">🍿</tg-emoji>' in cap, cap
    print("38. Premium emoji ID'si olindi va captionda <tg-emoji> bo'lib chiqdi ✔")

    await feed(cb(ADMIN, "emo_reset"))
    assert not EMOJI_IDS
    c = await feed(msg(USER, "1320"))
    assert "tg-emoji" not in find(c, "SendVideo").caption
    print("39. Oddiy emojiga qaytarildi ✔")

    await feed(cb(ADMIN, "stk_set"))
    c = await feed(msg(ADMIN, sticker=True))
    assert await db.get_setting("welcome_sticker") == "STK1"
    c = await feed(msg(USER, "/start"))
    assert [n for n, _ in c][0] == "SendSticker" and "xush kelibsiz" in texts(c), [n for n, _ in c]
    await feed(cb(ADMIN, "stk_off"))
    c = await feed(msg(USER, "/start"))
    assert not any(n == "SendSticker" for n, _ in c)
    print("40. Start stikeri o'rnatildi va o'chirildi ✔")

    c = await feed(cb(ADMIN, f"annsend:{new_id}:0"))
    assert "tanlanmagan" in texts(c), texts(c)
    await db.set_setting("announce_channel", "-1001")
    c = await feed(cb(ADMIN, f"annsend:{new_id}:0"))
    assert any(n == "SendPhoto" and getattr(m, "chat_id", None) == -1001 for n, m in c) or \
           any(n == "SendMessage" and getattr(m, "chat_id", None) == -1001 for n, m in c)
    print("41. Kinoni kanalga qayta e'lon qilish tugmasi ishladi ✔")

    # ---------- inline menyu ----------
    def cbdata(markup):
        return [b.callback_data for row in markup.inline_keyboard for b in row]

    c = await feed(cb(USER, "u:new:0"))
    e = find(c, "EditMessageText")
    assert "Yangi kinolar" in e.text and "u:home" in cbdata(e.reply_markup)
    assert any(d.startswith("get:") for d in cbdata(e.reply_markup))
    c = await feed(cb(USER, "u:top"))
    assert "ko'rilgan" in find(c, "EditMessageText").text
    c = await feed(cb(USER, "u:genres"))
    e = find(c, "EditMessageText")
    gdata = [d for d in cbdata(e.reply_markup) if d.startswith("u:g:")]
    assert gdata, cbdata(e.reply_markup)
    c = await feed(cb(USER, gdata[0]))
    e = find(c, "EditMessageText")
    assert any(d.startswith("get:") for d in cbdata(e.reply_markup)), cbdata(e.reply_markup)
    assert "u:genres" in cbdata(e.reply_markup) and "u:home" in cbdata(e.reply_markup)
    c = await feed(cb(USER, "u:find")); assert "yozib yuboring" in find(c, "EditMessageText").text
    c = await feed(cb(USER, "u:help")); assert "Yordam" in find(c, "EditMessageText").text
    c = await feed(cb(USER, "u:home")); assert "xush kelibsiz" in find(c, "EditMessageText").text
    c = await feed(cb(USER, "adm:home")); assert not any(n == "EditMessageText" for n, _ in c), "oddiy user admin panelni ocha olmasligi kerak"
    print("42. Foydalanuvchi inline menyusi (yangi/top/janr/qidiruv/yordam) ✔")

    c = await feed(cb(ADMIN, "adm:home"))
    e = find(c, "EditMessageText")
    assert "Admin panel" in e.text and {"adm:add", "adm:stats", "adm:tpl"} <= set(cbdata(e.reply_markup))
    for data, needle in [("adm:stats", "statistika"), ("adm:channels", "obuna"), ("adm:tpl", "shabloni"),
                         ("adm:ann", "E'lon kanali"), ("adm:emoji", "Premium emoji"), ("adm:movies", "Kinolar")]:
        c = await feed(cb(ADMIN, data))
        e = find(c, "EditMessageText")
        assert needle.lower() in e.text.lower(), (data, e.text)
        assert e.reply_markup.inline_keyboard[-1][0].callback_data == "adm:home", data
    c = await feed(cb(ADMIN, "adm:add"))
    assert "kinoning" in texts(c), texts(c)
    c = await feed(msg(ADMIN, "❌ Bekor qilish")); assert "Bekor qilindi" in texts(c)
    assert any(n == "SendMessage" and "Admin panel" in getattr(m, "text", "") for n, m in c)
    print("43. Admin paneli inline: hamma bo'limlar joyida ochiladi, «◀️ Admin panel» orqaga qaytaradi ✔")

    print("\nBARCHA OQIMLAR ISHLADI ✅")

try:
    asyncio.run(main())
finally:
    asyncio.run(db.close())
    if os.path.exists(DBF): os.unlink(DBF)
