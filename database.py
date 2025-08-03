import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import os

class DatabaseManager:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Создание таблицы для сообщений кураторов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS curator_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        curator_name TEXT NOT NULL,
                        discord_id TEXT NOT NULL,
                        message_date DATE NOT NULL,
                        message_hour INTEGER NOT NULL,
                        chats_count INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(curator_name, message_date, message_hour)
                    )
                ''')
                
                # Создание индексов для быстрого поиска
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_curator_date_hour 
                    ON curator_messages(curator_name, message_date, message_hour)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_date_hour 
                    ON curator_messages(message_date, message_hour)
                ''')
                
                conn.commit()
                logging.info("База данных инициализирована успешно")
                
        except Exception as e:
            logging.error(f"Ошибка при инициализации базы данных: {e}")
            raise
    
    def add_curator_message(self, curator_name: str, discord_id: str, 
                           message_date: str, message_hour: int, chats_count: int) -> bool:
        """Добавление сообщения куратора в базу данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO curator_messages 
                    (curator_name, discord_id, message_date, message_hour, chats_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (curator_name, discord_id, message_date, message_hour, chats_count))
                
                conn.commit()
                logging.info(f"Добавлено сообщение: {curator_name} - {chats_count} чатов за {message_date} {message_hour}:00")
                return True
                
        except Exception as e:
            logging.error(f"Ошибка при добавлении сообщения: {e}")
            return False
    
    def get_curator_stats_for_hour(self, message_date: str, message_hour: int) -> Dict[str, int]:
        """Получение статистики кураторов за конкретный час"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT curator_name, chats_count 
                    FROM curator_messages 
                    WHERE message_date = ? AND message_hour = ?
                    ORDER BY curator_name
                ''', (message_date, message_hour))
                
                results = cursor.fetchall()
                return {row[0]: row[1] for row in results}
                
        except Exception as e:
            logging.error(f"Ошибка при получении статистики: {e}")
            return {}
    
    def get_curator_history(self, curator_name: str, days: int = 7) -> List[Tuple]:
        """Получение истории сообщений куратора за последние дни"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT message_date, message_hour, chats_count, created_at
                    FROM curator_messages 
                    WHERE curator_name = ? 
                    AND message_date >= date('now', '-{} days')
                    ORDER BY message_date DESC, message_hour DESC
                '''.format(days), (curator_name,))
                
                return cursor.fetchall()
                
        except Exception as e:
            logging.error(f"Ошибка при получении истории: {e}")
            return []
    
    def get_daily_stats(self, date: str) -> Dict[str, int]:
        """Получение дневной статистики всех кураторов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT curator_name, SUM(chats_count) as total_chats
                    FROM curator_messages 
                    WHERE message_date = ?
                    GROUP BY curator_name
                    ORDER BY total_chats DESC
                ''', (date,))
                
                results = cursor.fetchall()
                return {row[0]: row[1] for row in results}
                
        except Exception as e:
            logging.error(f"Ошибка при получении дневной статистики: {e}")
            return {}
    
    def get_monthly_stats(self, year: int, month: int) -> Dict[str, int]:
        """Получение месячной статистики всех кураторов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT curator_name, SUM(chats_count) as total_chats
                    FROM curator_messages 
                    WHERE strftime('%Y', message_date) = ? 
                    AND strftime('%m', message_date) = ?
                    GROUP BY curator_name
                    ORDER BY total_chats DESC
                ''', (str(year), f"{month:02d}"))
                
                results = cursor.fetchall()
                return {row[0]: row[1] for row in results}
                
        except Exception as e:
            logging.error(f"Ошибка при получении месячной статистики: {e}")
            return {}
    
    def get_top_curators(self, days: int = 7, limit: int = 10) -> List[Tuple]:
        """Получение топ кураторов за период"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT curator_name, SUM(chats_count) as total_chats
                    FROM curator_messages 
                    WHERE message_date >= date('now', '-{} days')
                    GROUP BY curator_name
                    ORDER BY total_chats DESC
                    LIMIT ?
                '''.format(days), (limit,))
                
                return cursor.fetchall()
                
        except Exception as e:
            logging.error(f"Ошибка при получении топ кураторов: {e}")
            return []
    
    def delete_old_records(self, days: int = 90) -> int:
        """Удаление старых записей (старше указанного количества дней)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM curator_messages 
                    WHERE message_date < date('now', '-{} days')
                '''.format(days))
                
                deleted_count = cursor.rowcount
                conn.commit()
                logging.info(f"Удалено {deleted_count} старых записей")
                return deleted_count
                
        except Exception as e:
            logging.error(f"Ошибка при удалении старых записей: {e}")
            return 0
    
    def get_database_stats(self) -> Dict:
        """Получение статистики базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общее количество записей
                cursor.execute('SELECT COUNT(*) FROM curator_messages')
                total_records = cursor.fetchone()[0]
                
                # Количество уникальных кураторов
                cursor.execute('SELECT COUNT(DISTINCT curator_name) FROM curator_messages')
                unique_curators = cursor.fetchone()[0]
                
                # Дата самой старой записи
                cursor.execute('SELECT MIN(message_date) FROM curator_messages')
                oldest_date = cursor.fetchone()[0]
                
                # Дата самой новой записи
                cursor.execute('SELECT MAX(message_date) FROM curator_messages')
                newest_date = cursor.fetchone()[0]
                
                return {
                    'total_records': total_records,
                    'unique_curators': unique_curators,
                    'oldest_date': oldest_date,
                    'newest_date': newest_date
                }
                
        except Exception as e:
            logging.error(f"Ошибка при получении статистики БД: {e}")
            return {} 