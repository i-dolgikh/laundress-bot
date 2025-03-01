from datetime import datetime, timedelta

import aiogram
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from configs.config import SERVICE_SHEET_URL, SCHEDULE_SHEET_URL
import keyboards.keyboards as kb
from keyboards.keyboards import BookingCallback

from utils.sheets_utils import get_user_settings, connect_to_google_sheets, check_booking_limits, update_booking_info

booking_router = Router()

class BookingStates(StatesGroup):
    date = State()  # Ожидание ввода даты
    machine = State()  # Ожидание выбора машинки
    time = State()  # Ожидание выбора времени


@booking_router.message(Command('book'))
async def book_slot(message: types.Message, state: FSMContext):

    user_id = message.from_user.id
    client = await connect_to_google_sheets()

    user_settings = get_user_settings(client, SERVICE_SHEET_URL, user_id)

    reason = "Вы не можете забронировать слот. \nПричина: {} \nОбратитесь к старосте своего этажа. \n/contacts"
    try:  # Сделать грамотней
        overdue = datetime.strptime(user_settings['Дата последней оплаты'][3:], "%m.%y").date() < datetime.today().date() - timedelta(days=datetime.today().day)

        if user_settings['Причина отказа'] or overdue or not user_settings["Дата последней оплаты"]:
            await message.reply(reason.format(user_settings['Причина отказа'] if user_settings['Причина отказа'] else "Просрочен месяц оплаты"))
            await state.clear() # Зачем? ладно.
            return
    except ValueError:
        await message.reply(reason.format("Неизвестная ошибка")) #Пройдет тогда, когда юзера не будет в таблице или нет инфы об оплате (Но я не уверен)
        await state.clear() # Зачем? ладно.
        return


    """
    Проверка оплаты
    Забираем данные из schedule, сохраняем в FSM
    """

    worksheets = client.open_by_url(SCHEDULE_SHEET_URL)

    await state.update_data(client=client)
    await state.update_data(worksheets=worksheets)
    await state.update_data(user_settings=user_settings)

    await start_stage(message, state)


@booking_router.callback_query(F.data == "Back to start stage")
async def query_start_stage(query: CallbackQuery, state: FSMContext):
    await start_stage(query.message, state)


async def start_stage(message: types.Message, state: FSMContext):

    kb_builder_result = await kb.build_free_dates((await state.get_value("worksheets")).worksheets())

    if type(kb_builder_result) == str:
        await message.answer(text=kb_builder_result)
        return
    else:
        await state.update_data(test="Тестовая дата")
        try:
            await message.edit_text(text="Введите дату в формате DD.MM.YY или выберите из ближайших свободных", reply_markup=kb_builder_result)
        except aiogram.exceptions.TelegramBadRequest:
            await message.answer(text="Введите дату в формате DD.MM.YY или выберите из ближайших свободных", reply_markup=kb_builder_result)
        await state.update_data(date_kb = kb_builder_result)
        await state.set_state(BookingStates.date)  # Устанавливаем состояние "ожидание даты"


@booking_router.callback_query(BookingCallback.filter(F.stage == 2))
async def query_process_date(query: CallbackQuery,  callback_data: BookingCallback, state: FSMContext):
    date = callback_data.select

    await process_date(query.message, state, date)


@booking_router.message(BookingStates.date)
async def message_process_date(message: types.Message, state: FSMContext):
    date = message.text
    await message.bot.edit_message_text(text=f"Выбранная дата: {date}", message_id=message.message_id - 1, chat_id= message.chat.id) # Удаляем клавиатуру и выводим выбранную дату
    await process_date(message, state, date)

@booking_router.callback_query(F.data == "Back to machine stage")
async def query_start_stage(query: CallbackQuery, state: FSMContext):
    await process_date(query.message, state)


async def process_date(message: types.Message, state: FSMContext, booking_date=None):



    # try:
    if booking_date is None:
        booking_date = await state.get_value('selected_date')
    else:
        booking_date = datetime.strptime(booking_date, '%d.%m.%y').date()

    if booking_date < datetime.now().date():

        await message.reply("Нельзя бронировать прошедшие даты.")
        return
    if booking_date > datetime.now().date() + timedelta(days=30):
        await message.reply("Нельзя бронировать более чем за месяц.")
        return

    # Проверяем ограничения
    limit_error = check_booking_limits((await state.get_value('worksheets')), message.from_user.id, booking_date)
    if limit_error is not None:
        try:
            await message.edit_text(text=limit_error, reply_markup= (await state.get_value('date_kb')))
        except:
            await message.reply(limit_error)
            return

        await state.update_data(selected_date=booking_date)

        date_records = (await state.get_value("worksheets")).worksheet(booking_date.strftime('%d.%m.%y (%a)')).get_all_records()
        await state.update_data(date_records=date_records)
        keyboard = await kb.build_free_machine(date_records)

    # except ValueError:
    #     await message.reply("Неверный формат даты. Введите дату в формате DD.MM.YY")
    #     return


    """
    Проверяем ограничения на неделю (Если ограничение нарушено await query.message.edit_text("На эту неделю вы уже забронировали 2 слота" и завершаем сосотояние return))
    обновляем данные в FSM
    генерируем клавиатуру по машинкам
    регистрируем новое состояние
    """

    await message.edit_text(text=f'{await state.get_value("test")}, {booking_date}', reply_markup=keyboard) # тестовый
    await state.set_state()

@booking_router.callback_query(BookingCallback.filter(F.stage == 3))
async def process_machine(query: CallbackQuery, state: FSMContext, callback_data: BookingCallback):
    """
    Ловим callback со stage 3
    обновляем данные в FSM
    генерируем клавиатуру по слотам
    """
    await query.answer()
    await state.update_data(selected_machine=callback_data.select)


    data = await state.get_data()
    records = data.get('date_records')

    kb_builder_result = await kb.build_free_slots(records, callback_data.select)

    await query.message.edit_text(text="Выберите время", reply_markup=kb_builder_result)

@booking_router.callback_query(BookingCallback.filter(F.stage == 4))
async def process_time(query: CallbackQuery, state: FSMContext, callback_data: BookingCallback):
    await query.answer()
    selected_time = callback_data.select.replace('.', ':') # костыль, потому что callback_data жалуется, что в неё нельзя вставлять ":"
    await state.update_data(selected_time=selected_time)
    data = await state.get_data()
    """
    Ловим callback со stage 3
    достаем все данные из FSM
    кидаем в функцию записи
    ждем и отправляем статус успешности
    сообщаем пользователю
    """
    result = await update_booking_info(data)

    await query.message.edit_text(text=result)

    await state.clear()

