"""
Переделать все под asinc
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from configs.config import SERVICE_SHEET_URL, SERVICE_ACCOUNT_FILE

# Подключение к Google Sheets
async def connect_to_google_sheets(service_account_file = SERVICE_ACCOUNT_FILE):
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)
    client = gspread.authorize(creds)
    return client


# Получение листа по дате
def get_sheet_by_date(client, schedule_sheet_url, date): # Перенести логику создания в джобы
    sheet_name = date.strftime('%d.%m.%y (%a)')
    spreadsheet = client.open_by_url(schedule_sheet_url)
    try:
        return spreadsheet.worksheet(sheet_name)

    except gspread.exceptions.WorksheetNotFound: # Если не находим дату, создаем новый лист

        service_sheets = client.open_by_url(SERVICE_SHEET_URL)
        machines = service_sheets.worksheet("machine info").get_all_records()
        schedules = service_sheets.worksheet("schedule").get_all_records()

        try:
            start_time, end_time = None, None

            for schedule in schedules:
                if schedule["День недели"] == date.strftime('%a'):
                    start_time = datetime.strptime(schedule["Открытие"], "%H:%M")
                    end_time = datetime.strptime(schedule["Закрытие"], "%H:%M")
                    break

            if start_time is not None and end_time is not None:

                sheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=6)
                daily_schedule = [['Время', 'Машинка', 'Имя', 'Дата подачи', 'Комната', 'Telegram ID']]

                for machine in machines:
                    duration_slot = timedelta(minutes=machine["Шаг"])
                    slot = start_time
                    while slot <= end_time:
                        daily_schedule.append([slot.strftime("%H:%M"), machine["Машинка"]])
                        slot += duration_slot

                # Добавляем расписание
                sheet.append_rows(daily_schedule)
                # Скрываем от просмотра ID
                sheet.hide_columns(5, 6)

                return sheet

        except:  # Не работает в этот день недели
            return None


# Проверка ограничений на бронирование
def check_booking_limits(sheets, user_id, booking_date):
    week_start = booking_date - timedelta(days=booking_date.weekday())
    week_end = week_start + timedelta(days=6)

    weekly_bookings = 0
    total_booking = 0

    for sheet in sheets:
        records = sheet.get_all_records()
        for record in records:
            if record['Telegram ID'] == user_id:
                record_date = datetime.strptime(sheet.title, '%d.%m.%y (%a)').date()

                total_booking += 1

                if week_start <= record_date <= week_end:
                    weekly_bookings += 1



        if weekly_bookings >= 2:
            return "Вы уже забронировали 2 слота на эту неделю."
        elif total_booking >= 4:
            return "У вас уже есть 4 активных брони."

    return None


def update_booking_info(client, schedule_sheet_url, data):
    booking_date = data.get("booking_date")
    selected_machine = data.get("selected_machine")
    selected_time = data.get("selected_time")
    user_info = data.get("user_settings")

    # Логика записи в sheets

    test_mode = True
    if test_mode:
        return f"Тестовый режим: Бронирование завершено! Дата: {booking_date}, Время: {selected_time}, Машинка: {selected_machine}."
    else:
        return "Тестовый режим: Что-то пошло не так. Возможно, этот слот уже заняли"


# Обновление настроек пользователя
def update_user_settings(client, sheet_url, new_settings):
    """
    Обновляет настройки пользователя: обновляет настройки старого пользователя или добавляет нового.

    """
    settings_sheet = client.open_by_url(sheet_url).worksheet("users info")

    # Поиск старой записи пользователя
    id_cell = settings_sheet.find(query=str(new_settings[0]), in_column=1)
    if id_cell is not None:
        old_settings = list(settings_sheet.get_all_records()[id_cell.row - 2].values()) # '-2' - учитывая заголовок

        new_settings = [
            new_settings[record_index]
            if new_settings[record_index] != "" else old_settings[record_index]
            for record_index in range(len(new_settings))
        ]
        settings_sheet.batch_update([{'range': 'A' + str(id_cell.row), 'values': [new_settings]}])
    else:  # Добавляем пользователя
        settings_sheet.append_row(new_settings)


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