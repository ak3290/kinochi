# 🎬 Kinochi bot

Kino kodi yoki nomi bo'yicha qidiruv beruvchi Telegram bot. `aiogram 3` + `SQLite`.

## Imkoniyatlar

**Foydalanuvchi uchun**
- Kino **kodini** yuboradi — bot kinoni topib beradi
- Kino **nomini** yozadi — mos kinolar ro'yxati chiqadi
- Majburiy obuna kanallariga obuna bo'lmaguncha botdan foydalana olmaydi

**Admin uchun** (`.env` dagi `ADMINS` ro'yxatidagilar)
- Pastda `🛠 Admin panel` reply tugmasi chiqadi
- `➕ Kino qo'shish` — avval video yuboriladi, so'ng har bir maydon **alohida** so'raladi: nomi → tili → sifati → janri → ko'rish kategoriyasi → poster (rasm) → kod. Til/sifat/kategoriya uchun tayyor tugmalar bor, ixtiyoriy maydonlarni «⏭ O'tkazib yuborish» bilan tashlab ketish mumkin
- `🎬 Kinolar` — ro'yxat (sahifalab) yoki **kod/nom bo'yicha chaqirish**: bo'lim ochiq turganda kodni yozib yuborsangiz, kino kartochkasi darhol ochiladi. Har birini **tahrirlash** (kod / nom / til / sifat / janr / kategoriya) va **o'chirish** mumkin. Baza kattalashganda (1000+ kino) varaqlash o'rniga shu usul ishlatiladi
- `📊 Statistika` — foydalanuvchilar soni, bugun/hafta davomida qo'shilganlar, kinolar soni, jami ko'rishlar, top-5 kino
- `🧩 Shablon` — kino caption'ining ko'rinishini **bot ichidan** o'zgartirish: joriy shablon, jonli namuna, o'rin egallovchilar ro'yxati va standart holatga qaytarish tugmasi
- `📣 E'lon kanali` — kanalni tanlang: har bir yangi kino qo'shilganda shu kanalga **poster rasmi** va tagida «🆕 Yangi kino yuklandi!» + nomi, janri, tili, sifati, kategoriyasi, kodi bilan e'lon yuboriladi. Postda «🎬 Kinoni ko'rish» tugmasi bor — bosilsa bot ochilib, kino darhol yuboriladi. Poster berilmasa e'lon matn ko'rinishida ketadi
- `✨ Premium emoji` — caption va xabarlardagi belgilarni (🍿 🇺🇿 💾 🎞 ...) premium emoji bilan almashtirish: belgini tanlab, istalgan premium emojini yuborasiz, ID avtomatik olinadi. Shu yerda `/start` uchun **stiker** ham o'rnatiladi
- Kino kartochkasida `📣 Kanalga e'lon qilish` tugmasi — e'lonni qayta yuborish uchun
- `📢 Majburiy obuna` — **«Kanalni tanlash» tugmasi** orqali kanalni ro'yxatdan tanlab qo'shish (yoki username / ID / forward orqali) va o'chirish

## O'rnatish

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Sozlamalarni to'ldiring:

```bash
cp .env.example .env
```

`.env` ichida:

| O'zgaruvchi | Izoh |
|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) dan olinadi |
| `ADMINS` | Admin ID'lari, vergul bilan ([@userinfobot](https://t.me/userinfobot)) |
| `DB_PATH` | SQLite fayli (standart: `kinochi.db`) |

Ishga tushirish:

```bash
.venv/bin/python bot.py
```

## Testlar

Barcha asosiy oqimlar (kino qo'shish, qidiruv, tahrirlash, o'chirish, majburiy obuna) soxta Telegram sessiyasida tekshiriladi — Telegram'ga ulanish shart emas:

```bash
.venv/bin/python tests/test_flow.py
```

## Struktura

```
bot.py                      — kirish nuqtasi, dispatcher va middleware ulanadi
config.py                   — .env o'qish, ADMINS ro'yxati
database.py                 — SQLite (aiosqlite): users, movies, channels
keyboards.py                — reply va inline klaviaturalar
states.py                   — FSM holatlari
utils.py                    — obuna tekshiruvi, matn shablonlari
handlers/start.py           — /start, /help, obunani tekshirish
handlers/search.py          — kod va nom bo'yicha qidiruv
handlers/admin.py           — admin panel: kino, statistika, kanallar
middlewares/subscription.py — majburiy obuna filtri
```

## Muhim eslatmalar

- **Premium emoji** botdan faqat bot egasi Fragment'da qo'shimcha username sotib olgan bo'lsa ko'rinadi (Telegram qoidasi). Aks holda oddiy emoji chiqadi, xato bermaydi. Stiker esa har qanday botda ishlaydi.

- Majburiy obuna ishlashi uchun **bot kanalda admin bo'lishi shart**, aks holda tekshirib bo'lmaydi (bunday kanal jimgina o'tkazib yuboriladi — foydalanuvchi bloklanmaydi).
- «Kanalni tanlash» tugmasi Telegram'ning `request_chat` imkoniyatidan foydalanadi: ro'yxatda **faqat bot a'zo bo'lgan kanallar** ko'rinadi, shuning uchun botni avval kanalga admin qilib qo'shing.
- Kinolar Telegram serverida qoladi, bazada faqat `file_id` saqlanadi — shuning uchun baza juda yengil.
- Kodlar registrga bog'liq emas: `AB12` va `ab12` bir xil hisoblanadi.
- Caption shabloni bazada saqlanadi va `🧩 Shablon` bo'limidan tahrirlanadi. Standart ko'rinishi:

```
🍿 <b>{nom}</b>
➖➖➖➖➖➖➖➖➖➖➖➖
{tavsif}
🇺🇿 Tili: <b>{til}</b>
💾 Sifati: <b>{sifat}</b>
🎞 Janri: <b>{janr}</b>
⛔️ Kategoriya: <b>{kategoriya}</b>
➖➖➖➖➖➖➖➖➖➖➖➖
🗂 Kod: <code>{kod}</code>
👁 Ko'rildi: {korishlar} marta
🤖 {bot}
```

  O'rin egallovchilar: `{nom}` `{til}` `{sifat}` `{janr}` `{kategoriya}` `{kod}` `{korishlar}` `{bot}` `{tavsif}`.
  **Qiymati bo'sh bo'lgan o'rin egallovchi turgan qator butunlay tushib qoladi** — masalan kategoriya ko'rsatilmagan bo'lsa, o'sha qator chiqmaydi.
  Shablonni Telegram'ning o'z formatlashi bilan (qalin, kursiv) yoki to'g'ridan-to'g'ri HTML teglari bilan yozish mumkin. Saqlashdan oldin bot uni Telegram'ga yuborib tekshiradi — teglar buzuq bo'lsa saqlanmaydi.

- E'lon kanalida bot **admin** bo'lishi va «Post messages» huquqiga ega bo'lishi kerak. E'lon yuborilmasa ham kino saqlanadi, admin ogohlantiriladi.
- E'lon matni `utils.py` dagi `ANNOUNCE_TEMPLATE` da (qiymati bo'sh qator chiqmaydi).
- Qidiruv nom, janr va til bo'yicha ishlaydi.
- Eski bazaga yangi ustunlar (`language`, `quality`, `genre`, `category`, `poster_id`) avtomatik qo'shiladi — mavjud kinolar yo'qolmaydi.
