
from aiogram import Router, types
from aiogram.filters import Command

basic_router = Router()


# Команда /start
@basic_router.message(Command('start'))
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я бот для записи в прачечную общежития. "
                        "Используйте команду /book для бронирования.")

