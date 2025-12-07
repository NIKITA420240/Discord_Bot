import logging
import gspread
from datetime import datetime, timedelta
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials

# --- КОНСТАНТЫ ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'credentials.json'

MONTHS_GENITIVE = {
    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
    7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
}

# Для Рабочих часов (куда пишем)
DAYS_LOWER = {
    0: 'понедельник', 1: 'вторник', 2: 'среда', 3: 'четверг',
    4: 'пятница', 5: 'суббота', 6: 'воскресенье'
}

# Для Расписания (откуда читаем)
DAYS_CAPITAL = {
    0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг',
    4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
}

def get_sheet_name_text(dt):
    """Формат: '01 декабря - 07 декабря'"""
    start_of_week = dt - timedelta(days=dt.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_str = f"{start_of_week.day} {MONTHS_GENITIVE[start_of_week.month]}"
    end_str = f"{end_of_week.day} {MONTHS_GENITIVE[end_of_week.month]}"
    return f"{start_str} - {end_str}"

def get_sheet_name_numeric(dt):
    """Формат: '01.12.25-07.12.25'"""
    start_of_week = dt - timedelta(days=dt.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_str = start_of_week.strftime("%d.%m.%y")
    end_str = end_of_week.strftime("%d.%m.%y")
    return f"{start_str}-{end_str}"


# --- 1. СТАТИСТИКА ---
def _update_daily_stats(client, spreadsheet_id, curator_data, hour, day_str, month_str):
    try:
        today_sheet_name = f"{day_str} {month_str}"
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(today_sheet_name)
        except gspread.WorksheetNotFound:
            try:
                template = spreadsheet.worksheet("Шаблон")
                worksheet = template.duplicate(new_sheet_name=today_sheet_name)
                logging.info(f"Создан лист: {today_sheet_name}")
            except Exception as e:
                logging.error(f"Ошибка создания листа из шаблона: {e}", exc_info=True)
                return False

        all_data = worksheet.get_all_values()
        name_to_row = {}
        for idx, row in enumerate(all_data[1:], start=2):
            if row and row[0]:
                name_to_row[row[0].strip()] = idx
        
        updates = []
        col_idx = hour + 2 

        for name, count in curator_data.items():
            if name in name_to_row:
                row_idx = name_to_row[name]
                val = 'o' if count == 0 else ('c' if count == -1 else count)
                updates.append({
                    'range': rowcol_to_a1(row_idx, col_idx),
                    'values': [[val]]
                })
        
        if updates:
            worksheet.batch_update(updates)
            logging.info(f"Таблица 1 (Статистика): Обновлено {len(updates)} записей.")
        return True
    except Exception as e:
        logging.error(f"Ошибка в _update_daily_stats: {e}", exc_info=True)
        return False

# --- 2. РАБОЧИЕ ЧАСЫ ---
def _update_weekly_schedule(client, spreadsheet_id, curator_data, hour, dt_now):
    conflicts = [] 
    try:
        active_curators = [name for name, count in curator_data.items()] 
        
        # Текстовый формат имени листа
        sheet_name = get_sheet_name_text(dt_now) 
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            logging.info(f"Лист '{sheet_name}' не найден. Пробую создать из шаблона...")
            try:
                template = spreadsheet.worksheet("Шаблон")
                worksheet = template.duplicate(new_sheet_name=sheet_name)
                logging.info(f"Лист '{sheet_name}' успешно создан.")
            except Exception as e:
                logging.error(f"Ошибка при копировании шаблона: {e}", exc_info=True)
                return None # Возвращаем None при критической ошибке

        # День недели с маленькой буквы
        day_name = DAYS_LOWER[dt_now.weekday()] 
        
        try:
            cell_day = worksheet.find(day_name)
        except gspread.CellNotFound:
            logging.error(f"Ошибка: день '{day_name}' не найден в таблице рабочих часов.")
            return None # Критическая ошибка
        
        # Смещение +1 для старого формата
        row_idx = cell_day.row + 1 + hour 
        col_start = 2 
        MAX_SLOTS = 10 
        
        range_start = rowcol_to_a1(row_idx, col_start)
        range_end = rowcol_to_a1(row_idx, col_start + MAX_SLOTS - 1)
        cell_range = f"{range_start}:{range_end}"
        
        existing_values = worksheet.get(cell_range)
        current_row = existing_values[0] if existing_values else []
        while len(current_row) < MAX_SLOTS:
            current_row.append("")

        new_row = current_row[:] 

        for idx, name_in_sheet in enumerate(current_row):
            name_in_sheet = name_in_sheet.strip()
            if name_in_sheet: 
                if name_in_sheet in active_curators:
                    active_curators.remove(name_in_sheet)
                else:
                    conflicts.append(name_in_sheet)
        
        for worker in active_curators:
            written = False
            for idx, cell_val in enumerate(new_row):
                if cell_val == "": 
                    new_row[idx] = worker
                    written = True
                    break
            if not written:
                logging.warning(f"Не хватило места для записи {worker}")

        if new_row != current_row:
            worksheet.update(range_name=cell_range, values=[new_row], value_input_option='USER_ENTERED')
            logging.info(f"Таблица 2 (Рабочие часы): Обновлено на {hour}:00.")
        
        return conflicts # Возвращаем список (даже если пустой - это успех)

    except Exception as e:
        logging.error(f"Ошибка в _update_weekly_schedule: {e}", exc_info=True)
        return None # None означает, что произошел сбой

# --- ГЛАВНАЯ ФУНКЦИЯ (ИСПРАВЛЕНА ЛОГИКА ВОЗВРАТА) ---
def update_both_tables(spreadsheet_id_stats, spreadsheet_id_schedule, curator_data, hour, day_str, month_str, dt_now, update_schedule=False):
    """
    Возвращает кортеж: (Успешно_ли_все_прошло: bool, Список_конфликтов: list)
    """
    conflicts_found = [] 
    success_stats = False
    success_schedule = True # По умолчанию True, если не обновляем

    try:
        if not curator_data:
            return True, [] # Нет данных - считаем что всё ок

        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        client.set_timeout(60)

        # 1. Статистика
        success_stats = _update_daily_stats(client, spreadsheet_id_stats, curator_data, hour, day_str, month_str)
        if not success_stats:
            logging.error("Не удалось обновить Таблицу 1 (Статистика)")

        # 2. Рабочие часы
        if update_schedule:
            result = _update_weekly_schedule(client, spreadsheet_id_schedule, curator_data, hour, dt_now)
            if result is None:
                success_schedule = False
                logging.error("Не удалось обновить Таблицу 2 (Рабочие часы)")
            else:
                conflicts_found = result
                success_schedule = True
                logging.info("--> Обновление РАБОЧИХ ЧАСОВ выполнено.")
        else:
            logging.info("--> Обновление рабочих часов пропущено.")

        # Общий успех = (удалась статистика) И (удалось расписание)
        overall_success = success_stats and success_schedule
        return overall_success, conflicts_found 
        
    except Exception as e:
        logging.error(f"Критическая ошибка обновления таблиц: {e}", exc_info=True)
        return False, []

def get_scheduled_workers(client, spreadsheet_id, dt_now, hour):
    try:
        sheet_name = get_sheet_name_numeric(dt_now)
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        day_name = DAYS_CAPITAL[dt_now.weekday()]
        try:
            cell_day = worksheet.find(day_name)
        except gspread.CellNotFound:
            logging.error(f"День '{day_name}' не найден в расписании.")
            return []

        # --- ШАГ 1: Находим индексы колонок "Веб" ---
        web_indices = set()
        # Сканируем шапку (первые 10 строк)
        header_data = worksheet.get("A1:AX10")
        
        for row in header_data:
            # Если в строке есть "веб"
            if any("веб" in str(x).lower() for x in row):
                is_web_merge_block = False 
                for c_idx, val in enumerate(row):
                    txt = str(val).lower().strip()
                    
                    # Начало блока "Веб"
                    if "веб" in txt:
                        web_indices.add(c_idx)
                        is_web_merge_block = True
                    # Продолжение блока (пустая ячейка справа от Веб) - для объединенных ячеек
                    elif is_web_merge_block and txt == "":
                        web_indices.add(c_idx)
                    # Блок закончился (встретили другой текст)
                    elif txt != "":
                        is_web_merge_block = False
                
                if web_indices:
                    logging.info(f"Колонки вебинара (исключаем): {web_indices}")
                    break 
        # ---------------------------------------------

        target_row = cell_day.row + hour
        row_values = worksheet.row_values(target_row)
        
        if len(row_values) < 3: 
            return []
            
        # --- ШАГ 2: Собираем "Кого исключить" (кто на вебинаре) ---
        names_to_exclude = set()
        for idx in web_indices:
            # Проверяем, есть ли такой индекс в строке (строка может быть короче)
            if idx < len(row_values):
                val = row_values[idx].strip()
                if val:
                    names_to_exclude.add(val)
        
        if names_to_exclude:
            logging.info(f"На вебинаре в {hour}:00 -> {names_to_exclude}")

        # --- ШАГ 3: Собираем всех (Старший + Остальные) ---
        candidates = set()
        
        # 3.1 Старший (Колонка C = индекс 2)
        if len(row_values) > 2:
            senior = row_values[2].strip()
            if senior: candidates.add(senior)
            
        # 3.2 Остальные (начинаем с колонки E = индекс 4)
        # (Мы берем ВСЕХ, даже тех кто в колонке Веб, а потом отфильтруем)
        start_col = 4 
        for val in row_values[start_col:]:
            name = val.strip()
            if name:
                candidates.add(name)
        
        # --- ШАГ 4: Фильтрация (Все минус Вебинарщики) ---
        # Убираем тех, кто был найден в колонках Веб
        final_workers = list(candidates - names_to_exclude)
        
        return final_workers

    except Exception as e:
        logging.error(f"Ошибка чтения расписания: {e}", exc_info=True)
        return []

        
def get_senior_for_hour(client, spreadsheet_id, dt_now, hour):
    try:
        sheet_name = get_sheet_name_numeric(dt_now)
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            logging.error(f"Лист расписания '{sheet_name}' не найден.")
            return None

        day_name = DAYS_CAPITAL[dt_now.weekday()]
        try:
            cell_day = worksheet.find(day_name)
        except gspread.CellNotFound:
            logging.error(f"День '{day_name}' не найден.")
            return None
            
        target_row = cell_day.row + hour # Без +1 для нового формата
        senior_name = worksheet.cell(target_row, 3).value
        return senior_name.strip() if senior_name else None

    except Exception as e:
        logging.error(f"Ошибка получения старшего: {e}", exc_info=True)
        return None