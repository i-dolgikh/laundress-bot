
# bot.py

import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import TELEGRAM_API_TOKEN, GOOGLE_SHEET_URL, SERVICE_ACCOUNT_FILE
from utils import (
    connect_to_google_sheets,
    get_sheet_by_date,
    check_booking_limits,
    is_in_blacklist
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/bot.log"), logging.StreamHandler()]
)

# Инициализация бота
bot = Bot(token=TELEGRAM_API_TOKEN)
dp = Dispatcher(bot)

# Подключение к Google Sheets
client = connect_to_google_sheets(SERVICE_ACCOUNT_FILE)

# Инициализация планировщика задач
scheduler = AsyncIOScheduler()

# Команда /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я бот для записи в прачечную общежития. "
                        "Используйте команду /book для бронирования.")

# Команда /settings (настройка напоминаний)
@dp.message_handler(commands=['settings'])
async def settings(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("За день"), KeyboardButton("За 3 часа"), KeyboardButton("За час"), KeyboardButton("Отключить"))
    await message.reply("Выберите, когда вы хотите получать напоминания:", reply_markup=keyboard)

    # Сохраняем состояние для обработки выбора
    dp.register_message_handler(process_settings, state="*")

async def process_settings(message: types.Message):
    user_id = message.from_user.id
    choice = message.text

    # Сохраняем настройки пользователя (например, в отдельной таблице Google Sheets)
    settings_sheet = client.open_by_url(GOOGLE_SHEET_URL).worksheet("Settings")
    settings_sheet.append_row([user_id, choice])

    await message.reply(f"Напоминания установлены на: {choice}.")

# Задача для отправки напоминаний
async def send_reminders():
    today = datetime.now().date()
    sheets = client.open_by_url(GOOGLE_SHEET_URL).worksheets()

    for sheet in sheets:
        records = sheet.get_all_records()
        for record in records:
            booking_time = datetime.strptime(record['Время'], '%H:%M').time()
            booking_datetime = datetime.combine(today, booking_time)

            # Проверяем, нужно ли отправить напоминание
            if booking_datetime - timedelta(days=1) <= datetime.now() <= booking_datetime:
                user_id = record['ID Telegram']
                settings_sheet = client.open_by_url(GOOGLE_SHEET_URL).worksheet("Settings")
                user_settings = settings_sheet.get_all_records()

                reminder_time = None
                for setting in user_settings:
                    if setting['ID Telegram'] == user_id:
                        reminder_time = setting['Напоминание']
                        break

                if reminder_time == "За день" and booking_datetime - timedelta(days=1) <= datetime.now():
                    await bot.send_message(user_id, f"Напоминание: у вас забронировано время {record['Время']} на машинке {record['Машинка']}.")
                elif reminder_time == "За 3 часа" and booking_datetime - timedelta(hours=3) <= datetime.now():
                    await bot.send_message(user_id, f"Напоминание: у вас забронировано время {record['Время']} на машинке {record['Машинка']}.")
                elif reminder_time == "За час" and booking_datetime - timedelta(hours=1) <= datetime.now():
                    await bot.send_message(user_id, f"Напоминание: у вас забронировано время {record['Время']} на машинке {record['Машинка']}.")

# Запуск бота
if __name__ == '__main__':
    # Добавляем задачу для отправки напоминаний
    scheduler.add_job(send_reminders, 'interval', minutes=10)  # Проверяем каждые 10 минут
    scheduler.start()

    executor.start_polling(dp, skip_updates=True)
