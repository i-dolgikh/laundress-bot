from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from configs.config import client
from configs.config import SERVICE_SHEET_URL
from utils.sheets_utils import update_user_settings

settings_router = Router()


class SettingsStates(StatesGroup):
    room_number = State()
    name = State()
    notification = State()


# Команда /settings (настройка профиля)
@settings_router.message(Command('settings'))
async def settings(message: types.Message, state: FSMContext):

    await message.answer("Как вас зовут?")

    # Сохраняем состояние для обработки выбора
    await state.set_state(SettingsStates.name)

@settings_router.message(SettingsStates.name)
async def process_name(message: types.Message, state: FSMContext):

    await state.update_data(user_name = message.text)

    await message.answer("Введите номер своей комнаты")

    await state.set_state(SettingsStates.room_number)


@settings_router.message(SettingsStates.room_number)
async def process_name(message: types.Message, state: FSMContext):

    await state.update_data(user_room_number = message.text)

    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="За день"),
        KeyboardButton(text="За 3 часа"),
        KeyboardButton(text="За час")],
        [KeyboardButton(text="Отключить")]
    ], resize_keyboard=True)

    await message.answer("Выберите, когда вы хотите получать напоминания:", reply_markup=keyboard)

    await state.set_state(SettingsStates.notification)


@settings_router.message(SettingsStates.notification)
async def process_notification(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    choice = message.text

    # Проверяем допустимость выбора
    valid_choices = ["За день", "За 3 часа", "За час", "Отключить"]
    if choice not in valid_choices:
        await message.reply("Неверный выбор. Пожалуйста, выберите один из предложенных вариантов.")
        return

    # Обновляем настройки пользователя

    data = await state.get_data()
    name = data.get('user_name')
    room_number = data.get('user_room_number')

    update_user_settings(client, SERVICE_SHEET_URL, user_id, choice, name, room_number)

    await message.answer("Настройки обновлены", reply_markup=ReplyKeyboardRemove())

    if choice != 'Отключить':
        await message.reply(f"Напоминания будут приходить {choice.lower()} до стирки.")
    else:
        await message.reply(f"Напоминания отключены")

    await state.clear()
