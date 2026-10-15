from aiogram.fsm.state import State, StatesGroup


class AddMovie(StatesGroup):
    video = State()
    field = State()  # nom, til, sifat, janr, kategoriya — ketma-ket so'raladi
    poster = State()  # kanaldagi e'lon uchun rasm
    code = State()


class EditMovie(StatesGroup):
    value = State()


class FindMovie(StatesGroup):
    query = State()


class AddChannel(StatesGroup):
    channel = State()


class EditTemplate(StatesGroup):
    value = State()


class SetAnnounce(StatesGroup):
    channel = State()


class SetEmoji(StatesGroup):
    value = State()


class SetSticker(StatesGroup):
    value = State()
