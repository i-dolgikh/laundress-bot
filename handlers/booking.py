from datetime import datetime, timedelta

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from configs.config import SERVICE_SHEET_URL, SCHEDULE_SHEET_URL, client
from utils.sheets_utils import check_booking_limits, get_sheet_by_date, get_user_settings

booking_router = Router()


class BookingStates(StatesGroup):
    date = State()  # Ожидание ввода даты
    machine = State()  # Ожидание выбора машинки
    time = State()  # Ожидание выбора времени


# Команда /book (бронирование)
@booking_router.message(Command('book'))
async def book_slot(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    # Проверка "White ID List"
    user_settings = get_user_settings(client, SERVICE_SHEET_URL, user_id)

    reason = "Вы не можете забронировать слот. \nПричина: {} \nОбратитесь к старосте своего этажа. \n/contacts"
    try:  # Сделать грамотней
        overdue = datetime.strptime(user_settings['Дата последней оплаты'][3:], "%m.%y").date() < datetime.today().date() - timedelta(days=datetime.today().day)

        if user_settings['Причина отказа'] or overdue or not user_settings["Дата последней оплаты"]:
            await message.reply(reason.format(user_settings['Причина отказа'] if user_settings['Причина отказа'] else "Просрочен месяц оплаты"))
            await state.clear()
            return
    except:
        await message.reply(reason.format("Неизвестная ошибка")) #Пройдет тогда, когда юзера не будет в таблице или нет инфы об оплате (Но я не уверен)
        await state.clear()
        return

    await state.update_data(user_settings=user_settings) # Сохраняем user info в FSM
    await message.reply("Введите дату в формате DD.MM.YY:")
    await state.set_state(BookingStates.date)  # Устанавливаем состояние "ожидание даты"


# Обработка ввода даты
@booking_router.message(BookingStates.date)
async def process_date(message: types.Message, state: FSMContext):
    try:
        booking_date = datetime.strptime(message.text, '%d.%m.%y').date()
        if booking_date < datetime.now().date():
            await message.reply("Нельзя бронировать прошедшие даты.")
            return
        if booking_date > datetime.now().date() + timedelta(days=30):
            await message.reply("Нельзя бронировать более чем за месяц.")
            return

        # Проверяем ограничения
        limit_error = check_booking_limits(client, SCHEDULE_SHEET_URL, message.from_user.id, booking_date) #Включить на проде
        # if limit_error:
        #     await message.reply(limit_error)
        #     return

        """
        Взять sheet
        Проверить на доступные машинки
        Если нет сообщить и ожидать новую дату
        сохранить дату и sheet в FSM 
        Создать клавиатуру с доступными машинками 
        """

        # Сохраняем выбранную дату в FSM
        await state.update_data(booking_date=message.text)


        # Создаем клавиатуру с доступными машинками (Заглушка)
        buttons = [[KeyboardButton(text="Машинка 1")], [KeyboardButton(text="Машинка 2")], [KeyboardButton(text="Машинка 3")]]
        keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True) #Добавить актуально свободные машинки на дату


        await message.reply("Выберите машинку:", reply_markup=keyboard)
        await state.set_state(BookingStates.machine)# Переходим к следующему состоянию
    except ValueError:
        await message.reply("Неверный формат даты. Введите дату в формате DD.MM.YY")


# Обработка выбора машинки
@booking_router.message(BookingStates.machine)
async def process_machine(message: types.Message, state: FSMContext):
    await state.update_data(selected_machine=message.text[-1:]) #Сохранять в дб только номер машинки, а не select целиком
    # Получаем лист для выбранной даты
    # sheet = get_sheet_by_date(client, SCHEDULE_SHEET_URL, state.get_data().get("booking_date")) #Добавить актуально свободные слоты на дату + машинки

    # Генерируем доступные временные слоты (заглушка)
    available_slots = ["8:00", "8:40", "9:20", "00:40"]  # Пример слотов

    if not available_slots:
        await message.reply("На выбранную дату нет свободных слотов, выберите другую")
        return

    # Создаем клавиатуру с доступными слотами
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=slot) for slot in available_slots]],
        resize_keyboard=True
    )

    await message.reply("Выберите время:", reply_markup=keyboard)
    await state.set_state(BookingStates.time) # Переходим к следующему состоянию


# Обработка выбора времени
@booking_router.message(BookingStates.time)
async def process_time(message: types.Message, state: FSMContext):
    selected_time = message.text

    # Сохраняем выбранное время в FSM
    await state.update_data(selected_time=selected_time)

    await message.answer("Выполняю запрос...")

    # Получаем сохраненные данные из FSM
    data = await state.get_data()
    booking_date = data.get("booking_date")
    selected_machine = data.get("selected_machine")

    # Логика записи в Google Sheets
    # Перед отправкой проверить на конфликт (хер знает, сколько чел сидел в состоянии)
    sheet = get_sheet_by_date(client, SCHEDULE_SHEET_URL, datetime.strptime(booking_date, '%d.%m.%y').date())
    user_info = data.get("user_settings")
    sheet.append_row([selected_time, selected_machine, user_info['Имя'], booking_date, user_info['Номер комнаты'], message.from_user.id]) # Не добавлять, а изменять

    await message.answer(f"Бронирование завершено! Дата: {booking_date}, Время: {selected_time}, Машинка: {selected_machine}.", reply_markup=ReplyKeyboardRemove())
    await state.clear()  # Завершаем состояние
