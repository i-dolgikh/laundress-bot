import asyncio
from datetime import datetime, timedelta

import gspread
from configs.config import SCHEDULE_SHEET_URL, SERVICE_SHEET_URL

from utils.sheets_utils import get_users_settings


# Задача для отправки напоминаний
async def search_reminders(client, max_value = 72):
    try:
        sheets = client.open_by_url(SCHEDULE_SHEET_URL).worksheets()
        now = datetime.strptime(str(datetime.now())[:15] + "0", "%Y-%m-%d %H:%M")  # Костыль
        result = []


        users_settings = {settings['Telegram ID']:settings['Напоминание']
                          for settings in get_users_settings(client, SERVICE_SHEET_URL)
                          if settings['Напоминание'] != "off"}

        for sheet in sheets:

            booking_date = datetime.strptime(sheet.title, '%d.%m.%y (%a)').date()
            if datetime.today().date() + timedelta(hours=max_value) < booking_date:
                break
            elif datetime.today().date() <= booking_date:


                records = sheet.get_all_records()
                for record in records:
                    if record['Telegram ID'] in users_settings.keys():

                        try:
                            booking_time = datetime.strptime(record['Время'], '%H:%M').time()
                            booking_datetime = datetime.combine(booking_date, booking_time)
                        except ValueError:  # На ID нет записи (так быть не должно)
                            continue

                        if booking_datetime - timedelta(hours=users_settings[record['Telegram ID']]) == now:
                            result.append({
                                "user_id": record['Telegram ID'],
                                "text": f"Напоминание: {booking_datetime} у вас забронировано время на машинке {record['Машинка']}."
                                })
        return result
    except gspread.exceptions: #Если произошла ошибка (скорее всего со стороны сервера) пробуем раз еще через 10 секунд
        await asyncio.sleep(10)
        return await search_reminders(client)



# Задача для сортировки листов в таблице
async def sort_sheets_by_date(client, sheet_url=SERVICE_SHEET_URL): # Неактуально, удалить
    spreadsheet = await client.open_by_url(sheet_url)
    sheets = spreadsheet.worksheets()

    # Извлекаем даты из названий листов
    def extract_date_from_title(title):
        try:
            return datetime.strptime(title.split(' ')[0], '%d-%m-%y').date()
        except ValueError:
            return None

    # Сортируем листы по дате
    sorted_sheets = sorted(
        [(sheet, extract_date_from_title(sheet.title)) for sheet in sheets],
        key=lambda x: x[1] if x[1] else datetime(1970, 1, 1).date() # амбициозно, но сомнительно
    )

    # Переупорядочиваем листы
    for index, (sheet, _) in enumerate(sorted_sheets):
        spreadsheet.reorder_worksheet(sheet.id, index)


# Задача удаления листов предыдущей недели
async def delete_old_sheets(client, sheet_url=SERVICE_SHEET_URL): # Создавать листы для след недели
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    previous_week_start = week_start - timedelta(days=7)
    previous_week_end = previous_week_start + timedelta(days=6)

    spreadsheet = client.open_by_url(sheet_url)
    sheets = spreadsheet.worksheets()

    for sheet in sheets:
        try:
            sheet_date = datetime.strptime(sheet.title.split(' ')[0], '%d-%m-%y').date()
            if previous_week_start <= sheet_date <= previous_week_end:
                spreadsheet.del_worksheet(sheet)
        except ValueError:
            continue
