import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime, timedelta, timezone

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'credentials.json'

def update_google_sheets(spreadsheet_id, curator_data, hour, day, month_name):
    try:
        # Авторизация
        if (len(curator_data) == 0):
            logging.info(f"Кураторы за последний час не работали. {day} {month_name}, {hour}:00")
            return True
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        # Название листа: "18 июня"
        today_sheet_name = f"{day} {month_name}"

        logging.info(f"Текущее время: {datetime.now(timezone.utc) + timedelta(hours=3)}")
        logging.info(f"В поисках листа {today_sheet_name}")
        
        # Открываем таблицу
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(today_sheet_name)
            all_data = worksheet.get_all_values()
            logging.info(f"Найден лист: {today_sheet_name}")
        except gspread.WorksheetNotFound:
            # Лист не найден, создаем копию шаблонного листа
            logging.info(f"Лист {today_sheet_name} не найден, создаем копию шаблона...")
            try:
                template_worksheet = spreadsheet.worksheet("Шаблон")
                worksheet = template_worksheet.duplicate(new_sheet_name=today_sheet_name)
                logging.info(f"Создан новый лист: {today_sheet_name}")
            except gspread.WorksheetNotFound:
                logging.error(f"Шаблонный лист 'Шаблон' не найден. Создайте лист с названием 'Шаблон'.")
                return False
            except Exception as e:
                logging.error(f"Ошибка при создании копии шаблона: {str(e)}")
                return False

        # Получаем данные
        all_data = worksheet.get_all_values()
        
        # Словарь для поиска строк: имя → номер строки
        name_to_row = {}
        for idx, row in enumerate(all_data[1:], start=2):  # Пропускаем заголовок
            if row and row[0]:
                name_to_row[row[0].strip()] = idx
        
        # Обновление данных
        updates = []
        for name, count in curator_data.items():
            if name not in name_to_row:
                logging.info(f"Не найден куратор с именем {name}, ошибка.")
                return False
            
            row_idx = name_to_row[name]
            col_idx = hour + 2  # A=1, B=2 (час 0), C=3 (час 1)...
                
            # Записываем значение
            updates.append({
                'range': gspread.utils.rowcol_to_a1(row_idx, col_idx),
                'values': [[count]]
            })

            logging.info(f"Куратор {name} имеет {count} чатов, за время {day} {month_name}, {hour}:00")
        
        # Пакетное обновление
        if updates:
            worksheet.batch_update(updates)
        
        logging.info(f"Обновлено {len(updates)} ячеек")
        return True
        
    except Exception as e:
        logging.error(f"Ошибка при обновлении таблицы: {str(e)}", exc_info=True)
        return False