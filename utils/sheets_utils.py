
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# Подключение к Google Sheets
def connect_to_google_sheets(service_account_file):
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)
    client = gspread.authorize(creds)
    return client

# Получение листа по дате
def get_sheet_by_date(client, sheet_url, date):
    sheet_name = date.strftime('%d.%m.%y (%a)')
    spreadsheet = client.open_by_url(sheet_url)
    try:
        sheet = spreadsheet.worksheet(sheet_name)

    except gspread.exceptions.WorksheetNotFound:
        #Если не находим дату, создаем новый лист
        sheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=6)
        sheet.append_row(['Время', 'Машинка', 'Имя', 'Дата подачи', 'Комната', 'Telegram ID'])

        # Определяем диапазон столбца
        sheet_id = sheet._properties['sheetId']


        request_body_for_hide_id = {
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 5,  # Индекс столбца (начинается с 0)
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

# Проверка оплаты и причин отказа
def is_in_whitelist(client, sheet_url, user_id):
    users_info_sheet = client.open_by_url(sheet_url).worksheet("users info")
    records = users_info_sheet.get_all_records()
    for record in records:
        if record['Telegram ID'] == user_id:
            if record['Причина отказа']:
                return record['Причина отказа'] + "\n /contacts"
            elif datetime.strptime(record['Дата последней оплаты'][3:], "%m.%y").date() < datetime.today().date() - timedelta(days=datetime.today().day):
                return "Просрочен месяц оплаты, обратитесь к старосте своего этажа. \n /contacts"
            else:
                return None
    return "Произошла ошибка, обратитесь к старосте своего этажа. \n /contacts"

# Обновление настроек пользователя
def update_user_settings(client, sheet_url, user_id, notification, name, room_number):
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

def get_user_settings(client, sheet_url, user_id):
    settings_sheet = client.open_by_url(sheet_url).worksheet("users info")
    records = settings_sheet.get_all_records()

    # Поиск записи пользователя
    for record in records:
        if record['Telegram ID'] == user_id:
            return record

    return None