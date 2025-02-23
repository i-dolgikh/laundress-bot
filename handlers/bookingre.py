


from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.filters.callback_data import CallbackData
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, CallbackQuery

from configs.config import SERVICE_SHEET_URL, SCHEDULE_SHEET_URL, client

from keyboards.keyboards import build_free_machine, build_free_slots
from utils.sheets_utils import check_booking_limits, get_sheet_by_date, get_user_settings, update_booking_info

# booking_router = Router()


class BookingStates(StatesGroup):
    date = State()  # Ожидание ввода даты
    machine = State()  # Ожидание выбора машинки
    time = State()  # Ожидание выбора времени

class BookingCallback(CallbackData, prefix="booking"):
    type_select: str
    select: str


# Команда /book (бронирование)
@booking_router.message(Command('book'))
async def book_slot(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    user_settings = get_user_settings(client, SERVICE_SHEET_URL, user_id)

    reason = "Вы не можете забронировать слот. \nПричина: {} \nОбратитесь к старосте своего этажа. \n/contacts"
    try:  # Сделать грамотней
        overdue = datetime.strptime(user_settings['Дата последней оплаты'][3:], "%m.%y").date() < datetime.today().date() - timedelta(days=datetime.today().day)

        if user_settings['Причина отказа'] or overdue or not user_settings["Дата последней оплаты"]:
            await message.reply(reason.format(user_settings['Причина отказа'] if user_settings['Причина отказа'] else "Просрочен месяц оплаты"))
            await state.clear()
            return
    except ValueError:
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

        booking_records = get_sheet_by_date(client, SCHEDULE_SHEET_URL, booking_date).get_all_records()

        if booking_records:
            # Сохраняем выбранную дату и таблицу в FSM
            await state.update_data(booking_date=message.text)
            await state.update_data(booking_records=booking_records)
        else:
            await message.answer("На выбранную дату нет свободного времени")
            return



        # Создаем клавиатуру с доступными машинками
        keyboard = InlineKeyboardMarkup(inline_keyboard=await build_free_machine(booking_records), resize_keyboard=True)



        await message.reply("Выберите машинку:", reply_markup=keyboard)
        await state.set_state(BookingStates.machine)# Переходим к следующему состоянию
    except ValueError:
        await message.reply("Неверный формат даты. Введите дату в формате DD.MM.YY")


# Обработка выбора машинки
@booking_router.callback_query(BookingCallback.filter(F.type_select == "machine"))
@booking_router.message(BookingStates.machine)
async def process_machine(state: FSMContext, query: CallbackQuery, callback_data: BookingCallback):
    await state.update_data(selected_machine=message.text.split()[1])

    booking_records = await state.get_value('booking_records')

    # Генерируем доступные временные слоты
    available_slots = [slot for slot in [record['Время'] for record in booking_records if record['Машинка'] == int(message.text.split()[1])]]

    # Создаем клавиатуру с доступными слотами
    keyboard = InlineKeyboardMarkup(inline_keyboard= await build_free_slots(booking_records, ))

    await message.reply("Выберите время:", reply_markup=keyboard)
    await state.set_state(BookingStates.time) # Переходим к следующему состоянию


# Обработка выбора времени
@booking_router.message(BookingStates.time)
async def process_time(message: types.Message, state: FSMContext):
    selected_time = message.text

    # Сохраняем выбранное время в FSM
    await state.update_data(selected_time=selected_time) # Проверить на правильность времени (чтобы не было такого, что пользователь сам ввел время (ваще надо реализовать через колбеки))

    await message.answer("Выполняю запрос...")

    # Получаем сохраненные данные из FSM
    data = await state.get_data()

    status = update_booking_info(client, SCHEDULE_SHEET_URL, data)

    await message.answer(text=status, reply_markup=ReplyKeyboardRemove())
    await state.clear()  # Завершаем состояние
