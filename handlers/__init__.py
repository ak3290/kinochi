from aiogram import Router

from . import admin, menu, search, start


def get_routers() -> list[Router]:
    """Tartib muhim: admin router qidiruvdan oldin turadi."""
    return [start.router, menu.router, admin.router, search.router]
