from datetime import datetime, timedelta

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup


class BookingCallback(CallbackData, prefix="booking"):
	stage: int
	select: str


#Создаем клавиатуру с доступными датами
async def build_free_dates(worksheets):
	keyboard = InlineKeyboardBuilder()

	booking_dates = []

	for worksheet in worksheets:
		if ((datetime.strptime(worksheet.title, '%d.%m.%y (%a)').date() > datetime.now().date())
				and (not all(map(bool, [record["Telegram ID"] for record in worksheet.get_all_records()])))): # Проверяем, чтобы было свободное время на дату
			booking_dates.append(worksheet.title)
		if len(booking_dates) >= 6:
			break

	if not booking_dates:
		return "На ближайший месяц нет свободного времени"
	else:
		for booking_date in booking_dates:
			keyboard.add(InlineKeyboardButton(text=booking_date,
			                                  callback_data=BookingCallback(stage=2, select=booking_date[:8]).pack()))

	return keyboard.adjust(2).as_markup()


async def build_free_machine(records):
	keyboard = InlineKeyboardBuilder()

	for machine in set(records['Машинка'] for records in records if records['Telegram ID'] == ""):
		keyboard.add(InlineKeyboardButton(text="Машинка " + str(machine),
		                                  callback_data=BookingCallback(stage=3, select=str(machine)).pack()))

	keyboard.add(InlineKeyboardButton(text="Назад", callback_data="Back to start stage"))

	return keyboard.adjust(1).as_markup()


async def build_free_slots(records, machine):
	keyboard = InlineKeyboardBuilder()
	for record in records:

		if not record['Telegram ID'] and record['Машинка'] == int(machine):
			keyboard.add(InlineKeyboardButton(text=record['Время'],
			                                  callback_data=BookingCallback(
				                                  stage=4,
				                                  select=str(record['Время']).replace(':', '.')).pack())) # костыль, потому что callback_data жалуется, что в неё нельзя вставлять ":"

	keyboard.adjust(4)
	keyboard.row(InlineKeyboardButton(text="Назад", callback_data="Back to machine stage"))

	return keyboard.as_markup()


