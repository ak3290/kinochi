import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# .env dagi ADMINS="123456789,987654321" ko'rinishida bo'ladi
ADMINS: list[int] = [
    int(admin_id)
    for admin_id in os.getenv("ADMINS", "").replace(" ", "").split(",")
    if admin_id.isdigit()
]

# Baza oddiy fayl ko'rinishida saqlanadi
DB_PATH: str = os.getenv("DB_PATH", "kinochi.db")


def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env faylini to'ldiring (.env.example dan nusxa oling).")
