import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime, timedelta

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

# --- ЛОГИКА 2: НОВАЯ (Вертикальная структура + Сохранение выпадающих списков) ---
def _update_weekly_schedule(client, spreadsheet_id, curator_data, hour, dt_now):
    try:
        # 1. Подготовка даты (защита от строк)
        if isinstance(dt_now, str):
            try:
                dt_now = datetime.strptime(dt_now, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    dt_now = datetime.fromisoformat(dt_now.replace('Z', '+00:00'))
                except ValueError:
                    logging.warning(f"Не удалось прочитать дату '{dt_now}', использую текущее время.")
                    dt_now = datetime.now()

        # Берем только тех, кто работал
        active_curators = [name for name, count in curator_data.items()]
        
        # 2. Открытие листа
        sheet_name = get_weekly_sheet_name(dt_now) 
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            logging.warning(f"Таблица 2: Лист '{sheet_name}' не найден.")
            return False

        # 3. Поиск дня недели (Вертикальный поиск)
        day_name = DAYS_RU[dt_now.weekday()] 
        
        try:
            # Ищем ячейку с названием дня (например, "пятница")
            cell_day = worksheet.find(day_name)
        except gspread.CellNotFound:
            logging.error(f"Таблица 2: Не найден заголовок дня '{day_name}' в таблице.")
            return False

        day_start_row = cell_day.row
        
        # 4. Вычисление строки
        # Формула: Строка заголовка дня + 1 + час
        row_idx = day_start_row + 1 + hour
        col_idx = 2 # Столбец B

        # 5. Подготовка данных
        MAX_SLOTS = 10
        values = active_curators[:MAX_SLOTS]
        # Заполняем пустотой, чтобы стереть старые данные
        while len(values) < MAX_SLOTS: 
            values.append("") 

        # 6. Запись (USER_ENTERED сохраняет выпадающие списки)
        range_start = gspread.utils.rowcol_to_a1(row_idx, col_idx)
        range_end = gspread.utils.rowcol_to_a1(row_idx, col_idx + MAX_SLOTS - 1)
        range_name = f"{range_start}:{range_end}"
        
        worksheet.update(
            range_name=range_name, 
            values=[values], 
            value_input_option='USER_ENTERED'
        )
        
        logging.info(f"Таблица 2: Записано {len(active_curators)} имен в '{day_name}' {hour}:00 (строка {row_idx}).")
        return True
    except Exception as e:
        logging.error(f"Ошибка в _update_weekly_schedule: {e}", exc_info=True)
        return False


# --- ГЛАВНАЯ ФУНКЦИЯ ---
def update_both_tables(spreadsheet_id_stats, spreadsheet_id_schedule, curator_data, hour, day_str, month_str, dt_now, update_schedule=False):
    """
    Авторизуется и обновляет таблицы.
    update_schedule=True -> обновляет и статистику, и расписание (имена).
    update_schedule=False -> обновляет ТОЛЬКО статистику (цифры).
    """
    try:
        if not curator_data:
            return True

        # Авторизация один раз
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        client.set_timeout(60)

        # 1. Первая таблица (Статистика / Цифры) — ОБНОВЛЯЕМ ВСЕГДА
        res1 = _update_daily_stats(client, spreadsheet_id_stats, curator_data, hour, day_str, month_str)
        
        res2 = True
        # 2. Вторая таблица (Расписание / Имена) — ТОЛЬКО ЕСЛИ РАЗРЕШЕНО (ФЛАГ TRUE)
        if update_schedule:
            res2 = _update_weekly_schedule(client, spreadsheet_id_schedule, curator_data, hour, dt_now)
            logging.info("--> Обновление РАСПИСАНИЯ выполнено (по расписанию или вручную).")
        else:
            # Если флаг False, мы просто пропускаем этот шаг, чтобы не спамить в историю версий
            logging.info("--> Обновление расписания пропущено (экономим историю версий).")

        return res1 and res2 
        
    except Exception as e:
        logging.error(f"Критическая ошибка обновления таблиц: {e}")
        return False