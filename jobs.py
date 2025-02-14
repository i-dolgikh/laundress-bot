from datetime import datetime, timedelta
from configs.config import SCHEDULE_SHEET_URL, SERVICE_SHEET_URL

# Задача для отправки напоминаний
def search_reminders(client): #Джоба срабатывает несколько раз. Не работает, если джоба попадает на другой день
    today = datetime.now().date()
    sheets = client.open_by_url(SCHEDULE_SHEET_URL).worksheets()
    for sheet in sheets:

        records = sheet.get_all_records()
        result = []
        result = [{
            "user_id": 1401620696,
            "text": f"Тестовое уведомление {datetime.now()}."
            }] #test result!!!


        for record in records:
            booking_time = datetime.strptime(record['Время'], '%H:%M').time()
            booking_datetime = datetime.combine(today, booking_time) #Надо комбинить не с сегодня, а с датой на которое установлен booking

            # Проверяем, нужно ли отправить напоминание
            if booking_datetime - timedelta(days=1) <= datetime.now() <= booking_datetime:
                user_id = record['Telegram ID']
                settings_sheet = client.open_by_url(SERVICE_SHEET_URL).worksheet("notifications")
                user_settings = settings_sheet.get_all_records()

                reminder_time = None
                for setting in user_settings:
                    if setting['Telegram ID'] == user_id:
                        reminder_time = setting['Напоминание']
                        break

                if ((reminder_time == "За день" and booking_datetime - timedelta(days=1) <= datetime.now()
                        or reminder_time == "За 3 часа" and booking_datetime - timedelta(hours=3) <= datetime.now())
                        or reminder_time == "За час" and booking_datetime - timedelta(hours=1) <= datetime.now()):
                    result.append({
                        "user_id": user_id,
                        "text": f"Напоминание: у вас забронировано время {record['Время']} на машинке {record['Машинка']}."
                        })
        return result


# Задача для сортировки листов в таблице
def sort_sheets_by_date(client, sheet_url=SERVICE_SHEET_URL): # ЭТО БЕТКА! ПРОТЕСТИТЬ
    spreadsheet = client.open_by_url(sheet_url)
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
def delete_old_sheets(client, sheet_url=SERVICE_SHEET_URL): # ЭТО БЕТКА! ПРОТЕСТИТЬ
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    previous_week_start = week_start - timedelta(days=7)
    previous_week_end = previous_week_start + timedelta(days=6)

    spreadsheet = client.open_by_url(sheet_url)
    sheets = spreadsheet.worksheets()

    for sheet in sheets:
        try:
            sheet_date = datetime.strptime(sheet.title.split(' ')[0], '%Y-%m-%d').date()
            if previous_week_start <= sheet_date <= previous_week_end:
                spreadsheet.del_worksheet(sheet)
        except ValueError:
            continue
