from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup


class BookingCallback(CallbackData, prefix="booking"):
	stage: int
	select: str = None


#Создаем клавиатуру с доступными датами
async def build_free_date(worksheets):
	keyboard = InlineKeyboardBuilder()

	booking_dates = []

	for worksheet in worksheets[:6]:
		if not all(map(bool, [record["Telegram ID"] for record in worksheet.get_all_records()])):
			booking_dates.append(worksheet.title)

	if not booking_dates:
		return "На ближайший месяц нет свободного времени"
	else:
		for booking_date in booking_dates:
			keyboard.add(InlineKeyboardButton(text=booking_date,
			                                  callback_data=BookingCallback(stage=2, select=booking_date).pack()))

	return keyboard.adjust(2).as_markup()


async def build_free_machine(records):
	keyboard = InlineKeyboardBuilder()

	for machine in set(records['Машинка'] for records in records if records['Telegram ID'] == ""):
		keyboard.add(InlineKeyboardButton(text="Машинка " + str(machine),
		                                  callback_data=BookingCallback(stage=3, select=str(machine)).pack()))

	keyboard.add(InlineKeyboardButton(text="Назад", callback_data="Back to start stage"))

	return keyboard.adjust(1).as_markup()


async def build_free_slots(records):
	pass
