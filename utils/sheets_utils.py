
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from configs.config import SERVICE_SHEET_URL

# Подключение к Google Sheets
def connect_to_google_sheets(service_account_file):
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)
    client = gspread.authorize(creds)
    return client

# Получение листа по дате
def get_sheet_by_date(client, schedule_sheet_url, date):
    sheet_name = date.strftime('%d.%m.%y (%a)')
    spreadsheet = client.open_by_url(schedule_sheet_url)
    try:
        sheet = spreadsheet.worksheet(sheet_name)

    except gspread.exceptions.WorksheetNotFound: # Если не находим дату, создаем новый лист

        sheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=6)
        sheet.append_row(['Время', 'Машинка', 'Имя', 'Дата подачи', 'Комната', 'Telegram ID'])

        # Скрываем от просмотра ID
        sheet_id = sheet._properties['sheetId']
        request_body_for_hide_id = {
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 5,  # Индекс столбца (с 0)
                            "endIndex": 6  # Конечный индекс (не включается)
                        },
                        "properties": {
                            "hiddenByUser": True  # Скрываем столбец
                        },
                        "fields": "hiddenByUser"
                    }
                }
            ]
        }

        # Отправляем запрос на обновление свойств
        spreadsheet.batch_update(request_body_for_hide_id)

        """
        Получаем данные о расписании дня недели
        Получаем данные о машинках и их шагах
        Заполняем слоты
        !!!Нерабочие дни надо словить через try
        """

        service_sheets = client.open_by_url(SERVICE_SHEET_URL)
        machines = service_sheets.worksheet("machine info").get_all_records()
        schedules = service_sheets.worksheet("schedule").get_all_records()

        start_time = None
        end_time = None

        try:
            for schedule in schedules:
                if schedule["День недели "] == date.strftime('%a'):
                    start_time = datetime.strptime(schedule["Открытие"], "%H:%M")
                    end_time = datetime.strptime(schedule["Закрытие"], "%H:%M")
                    break
        except: # Не работает в этот день недели
            return sheet

        for machine in machines:
            duration_slot = timedelta(minutes=machine["Шаг"])
            slot = start_time
            while slot + duration_slot <= end_time:
                sheet.append_row([slot.strftime("%H:%M"), machine["Машинка"]])
                slot += duration_slot


    return sheet

# Проверка ограничений на бронирование
def check_booking_limits(client, sheet_url, user_id, booking_date): # Оптимизировать
    week_start = booking_date - timedelta(days=booking_date.weekday())
    week_end = week_start + timedelta(days=6)

    weekly_bookings = 0
    sheets = client.open_by_url(sheet_url).worksheets()
    for sheet in sheets:
        records = sheet.get_all_records()
        for record in records:
            if record['Telegram ID'] == user_id:
                record_date = datetime.strptime(str(sheet).split("'")[1], '%d.%m.%y (%a)').date()

                if week_start <= record_date <= week_end:
                    weekly_bookings += 1
                elif week_end < record_date:
                    break


    if weekly_bookings >= 2:
        return "Вы уже забронировали 2 слота на эту неделю."

    return None


# Обновление настроек пользователя
def update_user_settings(client, sheet_url, user_id, notification, name, room_number): # Реализовать через изменение, а не удаление
    """
    Обновляет настройки пользователя: удаляет старые настройки и добавляет новые.
    """
    settings_sheet = client.open_by_url(sheet_url).worksheet("users info")
    records = settings_sheet.get_all_records()

    # Поиск и удаление старой записи пользователя
    for i, record in enumerate(records):
        if record['Telegram ID'] == user_id:
            # Удаляем строку (учитываем заголовок)
            settings_sheet.delete_rows(i + 2)
            break

    settings_sheet.append_row([user_id, name, room_number, '', notification])


def get_user_settings(client, service_sheet_url, user_id):
    settings_sheet = client.open_by_url(service_sheet_url).worksheet("users info")
    records = settings_sheet.get_all_records()

    # Поиск записи пользователя
    for record in records:
        if record['Telegram ID'] == user_id:
            return record

    return None

def get_users_settings(client, service_sheet_url):
    settings_sheet = client.open_by_url(service_sheet_url).worksheet("users info")
    return settings_sheet.get_all_records()