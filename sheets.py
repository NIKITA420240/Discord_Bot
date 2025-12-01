import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime, timedelta
from gspread.utils import rowcol_to_a1

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'credentials.json'

# Константы для дат
MONTHS_GENITIVE = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
    7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
}

DAYS_RU = {
    0: 'понедельник', 1: 'вторник', 2: 'среда', 3: 'четверг',
    4: 'пятница', 5: 'суббота', 6: 'воскресенье'
}

def get_weekly_sheet_name(dt):
    """Вычисляет название листа для недели: '24 ноября - 30 ноября'"""
    start_of_week = dt - timedelta(days=dt.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_str = f"{start_of_week.day} {MONTHS_GENITIVE[start_of_week.month]}"
    end_str = f"{end_of_week.day} {MONTHS_GENITIVE[end_of_week.month]}"
    return f"{start_str} - {end_str}"

# --- ЛОГИКА 1: СТАРАЯ (Количество чатов) ---
def _update_daily_stats(client, spreadsheet_id, curator_data, hour, day_str, month_str):
    try:
        today_sheet_name = f"{day_str} {month_str}" # Пример: "28 ноября"
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(today_sheet_name)
        except gspread.WorksheetNotFound:
            # Логика создания копии шаблона
            try:
                template = spreadsheet.worksheet("Шаблон")
                worksheet = template.duplicate(new_sheet_name=today_sheet_name)
                logging.info(f"Создан лист: {today_sheet_name}")
            except Exception as e:
                logging.error(f"Ошибка создания листа из шаблона: {e}")
                return False

        all_data = worksheet.get_all_values()
        name_to_row = {}
        # Индексируем имена (предполагаем, что имена в столбце A, начиная со 2 строки)
        for idx, row in enumerate(all_data[1:], start=2):
            if row and row[0]:
                name_to_row[row[0].strip()] = idx
        
        updates = []
        col_idx = hour + 2 # A=1, B=0ч, C=1ч... (проверьте смещение в вашей таблице!)

        for name, count in curator_data.items():
            if name in name_to_row:
                row_idx = name_to_row[name]
                val = 'o' if count == 0 else ('c' if count == -1 else count)
                updates.append({
                    'range': gspread.utils.rowcol_to_a1(row_idx, col_idx),
                    'values': [[val]]
                })
        
        if updates:
            worksheet.batch_update(updates)
            logging.info(f"Таблица 1 (Статистика): Обновлено {len(updates)} записей.")
        return True
    except Exception as e:
        logging.error(f"Ошибка в _update_daily_stats: {e}")
        return False

def _update_weekly_schedule(client, spreadsheet_id, curator_data, hour, dt_now):
    """
    Умное обновление расписания:
    1. Ищет лист недели. Если нет — создает копию из "Шаблон".
    2. Читает текущие записи.
    3. Дописывает работающих в пустые слоты, фиксирует конфликты.
    """
    conflicts = [] 
    
    try:
        # 1. Подготовка
        active_curators = [name for name, count in curator_data.items()] 
        
        sheet_name = get_weekly_sheet_name(dt_now) 
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # --- ИЗМЕНЕНИЕ: Логика создания листа ---
        try:
            # Пытаемся открыть существующий лист
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            logging.info(f"Лист '{sheet_name}' не найден. Пробую создать из шаблона...")
            try:
                # Если листа нет, ищем Шаблон и копируем
                template = spreadsheet.worksheet("Шаблон")
                worksheet = template.duplicate(new_sheet_name=sheet_name)
                logging.info(f"Лист '{sheet_name}' успешно создан из шаблона.")
            except gspread.WorksheetNotFound:
                logging.error("Критическая ошибка: В таблице нет листа 'Шаблон'!")
                return []
            except Exception as e:
                logging.error(f"Ошибка при копировании шаблона: {e}")
                return []
        # ---------------------------------------

        # 2. Поиск строки и диапазона
        day_name = DAYS_RU[dt_now.weekday()] 
        try:
            cell_day = worksheet.find(day_name)
        except gspread.CellNotFound:
            logging.error(f"Ошибка: На листе '{sheet_name}' (или в шаблоне) не найден день '{day_name}'.")
            return []
        
        row_idx = cell_day.row + 1 + hour
        col_start = 2 # Столбец B
        MAX_SLOTS = 10 
        
        range_start = rowcol_to_a1(row_idx, col_start)
        range_end = rowcol_to_a1(row_idx, col_start + MAX_SLOTS - 1)
        cell_range = f"{range_start}:{range_end}"
        
        # 3. ЧИТАЕМ текущие значения
        existing_values = worksheet.get(cell_range)
        
        current_row = existing_values[0] if existing_values else []
        while len(current_row) < MAX_SLOTS:
            current_row.append("")

        new_row = current_row[:] 

        # 4. Анализ занятых слотов
        for idx, name_in_sheet in enumerate(current_row):
            name_in_sheet = name_in_sheet.strip()
            
            if name_in_sheet: 
                if name_in_sheet in active_curators:
                    active_curators.remove(name_in_sheet)
                else:
                    conflicts.append(name_in_sheet)
        
        # 5. Дозапись (Append)
        for worker in active_curators:
            written = False
            for idx, cell_val in enumerate(new_row):
                if cell_val == "": 
                    new_row[idx] = worker
                    written = True
                    break
            
            if not written:
                logging.warning(f"Не хватило места (MAX_SLOTS) для записи {worker}")

        # 6. Запись обновленной строки
        if new_row != current_row:
            worksheet.update(
                range_name=cell_range, 
                values=[new_row], 
                value_input_option='USER_ENTERED'
            )
            logging.info(f"Таблица 2: Обновлено расписание на {hour}:00.")
        
        return conflicts

    except Exception as e:
        logging.error(f"Ошибка в _update_weekly_schedule: {e}", exc_info=True)
        return []


# --- ГЛАВНАЯ ФУНКЦИЯ ---
def update_both_tables(spreadsheet_id_stats, spreadsheet_id_schedule, curator_data, hour, day_str, month_str, dt_now, update_schedule=False):
    """
    Авторизуется и обновляет таблицы.
    Возвращает список конфликтов (имен), если они есть.
    """
    conflicts_found = [] # Инициализируем пустой список сразу
    
    try:
        if not curator_data:
            return [] 

        # Авторизация
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        client.set_timeout(60)

        # 1. Обновляем статистику (всегда)
        _update_daily_stats(client, spreadsheet_id_stats, curator_data, hour, day_str, month_str)
        
        # 2. Обновляем расписание (только если нужно)
        if update_schedule:
            conflicts_found = _update_weekly_schedule(client, spreadsheet_id_schedule, curator_data, hour, dt_now)
            logging.info("--> Обновление РАСПИСАНИЯ выполнено.")
        else:
            logging.info("--> Обновление расписания пропущено.")

        return conflicts_found 
        
    except Exception as e:
        logging.error(f"Критическая ошибка обновления таблиц: {e}")
        return []

def get_scheduled_workers(client, spreadsheet_id, dt_now, hour):
    """
    Возвращает список имен, записанных в расписании на конкретный час.
    Нужно для проверки прогульщиков (Feature 1).
    """
    try:
        sheet_name = get_weekly_sheet_name(dt_now)
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        day_name = DAYS_RU[dt_now.weekday()]
        cell_day = worksheet.find(day_name)
        
        target_row = cell_day.row + 1 + hour
        # Читаем строку (пропуская колонку А)
        row_values = worksheet.row_values(target_row)
        
        if len(row_values) < 2:
            return []
            
        # Очищаем от пустых строк и пробелов
        scheduled_names = [n.strip() for n in row_values[1:] if n.strip()]
        return scheduled_names
    except Exception as e:
        logging.error(f"Ошибка чтения расписания: {e}")
        return []


def get_senior_for_hour(client, spreadsheet_id, dt_now, hour):
    """
    Возвращает имя старшего куратора (из колонки C) на заданный час.
    """
    try:
        sheet_name = get_weekly_sheet_name(dt_now)
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            return None

        day_name = DAYS_RU[dt_now.weekday()]
        
        # Находим день
        try:
            cell_day = worksheet.find(day_name)
        except gspread.CellNotFound:
            return None
            
        # Вычисляем строку (День + 1 строка заголовка + час)
        target_row = cell_day.row + 1 + hour
        
        # Колонка C (STARший) — это 3-я колонка
        senior_name = worksheet.cell(target_row, 3).value
        
        return senior_name.strip() if senior_name else None

    except Exception as e:
        logging.error(f"Ошибка получения старшего куратора: {e}")
        return None