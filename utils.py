
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
    sheet_name = date.strftime('%Y-%m-%d (%a)')
    try:
        sheet = client.open_by_url(sheet_url).worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open_by_url(sheet_url).add_worksheet(title=sheet_name, rows=100, cols=6)
        sheet.append_row(['Время', 'Машинка', 'Имя', 'Дата подачи', 'Комната', 'ID Telegram'])
    return sheet

# Проверка ограничений на бронирование
def check_booking_limits(client, sheet_url, user_id, booking_date):
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    weekly_bookings = 0
    monthly_bookings = 0
    sheets = client.open_by_url(sheet_url).worksheets()
    for sheet in sheets:
        records = sheet.get_all_records()
        for record in records:
            if record['ID Telegram'] == user_id:
                record_date = datetime.strptime(record['Дата подачи'], '%Y-%m-%d').date()
                if week_start <= record_date <= week_end:
                    weekly_bookings += 1
                if today <= record_date <= booking_date:
                    monthly_bookings += 1

    if weekly_bookings >= 2:
        return "Вы уже забронировали 2 слота на эту неделю."
    if monthly_bookings >= 1:
        return "Вы уже забронировали слот более чем за месяц."
    return None

# Проверка "Black ID List"
def is_in_blacklist(client, sheet_url, user_id):
    blacklist_sheet = client.open_by_url(sheet_url).worksheet("Black ID List")
    records = blacklist_sheet.get_all_records()
    for record in records:
        if record['ID Telegram'] == user_id:
            return record['Причина']
    return None