

# Логирование, время, async
import logging
from datetime import datetime, timedelta
import asyncio

# Работа с tg API
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Библиотека для джобов
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Конфиги
from configs.config import TELEGRAM_API_TOKEN

# Утилиты для google sheets


# Импорт джобов
from jobs import (
    search_reminders,
    delete_old_sheets,
    sort_sheets_by_date
)

# Роутеры
from handlers.settings import settings_router
from handlers.booking import booking_router
from handlers.basic import basic_router
from utils.sheets_utils import connect_to_google_sheets

# Тестовые импорты


# Инициализация бота
storage = MemoryStorage()
bot = Bot(token=TELEGRAM_API_TOKEN)
dp = Dispatcher(storage=storage)


# Инициализация планировщика задач
scheduler = AsyncIOScheduler()



async def send_reminders_job():
    client = await connect_to_google_sheets()
    reminders = await search_reminders(client)

    for reminder in reminders:
        await bot.send_message(reminder["user_id"], reminder["text"])

async def sorted_job():
    try:
        client = await connect_to_google_sheets()
        await sort_sheets_by_date(client)
    except:
        pass

async def delite_old_job():
    try:
        client = await connect_to_google_sheets()
        await delete_old_sheets(client)
    except:
        pass

# Запуск бота
async def main():

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler("configs/bot.log"), logging.StreamHandler()]
    )

    # Задача для отправки напоминаний (каждые 10 минут в **:*0)
    scheduler.add_job(send_reminders_job,
        'interval',
                      minutes=10,
                      next_run_time=datetime.strptime(str(datetime.now())[:15] + "0","%Y-%m-%d %H:%M") + timedelta(minutes=10)  # костыль из-за старой версии библиотеки
                      )

    #Задача для удаления старых листов (каждые 7 дней по понедельникам в 01:00)
    scheduler.add_job(
        delite_old_job,
        'cron',
        day_of_week = 0,
        hour = 1
    )

    #Задача для сортировки листов (каждый день в 01:00)
    scheduler.add_job(
        sorted_job,
        'cron',
        hour = 1
    )

    scheduler.start()

    dp.include_routers( basic_router, settings_router, booking_router)

    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
