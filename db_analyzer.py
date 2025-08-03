#!/usr/bin/env python3
"""
Анализатор базы данных Discord бота
Позволяет просматривать, анализировать и экспортировать данные
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import argparse
import json
import sys
from typing import Dict, List, Tuple

class DatabaseAnalyzer:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        
    def check_connection(self) -> bool:
        """Проверяет подключение к базе данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                print(f"✅ Подключение к БД успешно. Найдено таблиц: {len(tables)}")
                return True
        except Exception as e:
            print(f"❌ Ошибка подключения к БД: {e}")
            return False
    
    def get_database_info(self) -> Dict:
        """Получает общую информацию о базе данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общее количество записей
                cursor.execute("SELECT COUNT(*) FROM curator_messages")
                total_records = cursor.fetchone()[0]
                
                # Уникальные кураторы
                cursor.execute("SELECT COUNT(DISTINCT curator_name) FROM curator_messages")
                unique_curators = cursor.fetchone()[0]
                
                # Диапазон дат
                cursor.execute("SELECT MIN(message_date), MAX(message_date) FROM curator_messages")
                date_range = cursor.fetchone()
                
                # Общее количество чатов
                cursor.execute("SELECT SUM(chats_count) FROM curator_messages")
                total_chats = cursor.fetchone()[0] or 0
                
                return {
                    "total_records": total_records,
                    "unique_curators": unique_curators,
                    "date_range": date_range,
                    "total_chats": total_chats
                }
        except Exception as e:
            print(f"❌ Ошибка получения информации: {e}")
            return {}
    
    def show_recent_data(self, limit: int = 10) -> None:
        """Показывает последние записи"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT curator_name, message_date, message_hour, chats_count, created_at
                FROM curator_messages
                ORDER BY created_at DESC
                LIMIT ?
                """
                df = pd.read_sql_query(query, conn, params=(limit,))
                
                if df.empty:
                    print("📭 База данных пуста")
                    return
                
                print(f"📊 Последние {len(df)} записей:")
                print("=" * 80)
                for _, row in df.iterrows():
                    print(f"👤 {row['curator_name']:20} | 📅 {row['message_date']} {row['message_hour']:02d}:00 | 💬 {row['chats_count']:3d} чатов | 🕐 {row['created_at']}")
                print("=" * 80)
                
        except Exception as e:
            print(f"❌ Ошибка получения данных: {e}")
    
    def get_curator_stats(self, curator_name: str = None, days: int = 7) -> None:
        """Показывает статистику кураторов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if curator_name:
                    # Статистика конкретного куратора
                    query = """
                    SELECT message_date, message_hour, chats_count
                    FROM curator_messages
                    WHERE curator_name = ? AND message_date >= date('now', '-{} days')
                    ORDER BY message_date DESC, message_hour DESC
                    """.format(days)
                    df = pd.read_sql_query(query, conn, params=(curator_name,))
                    
                    if df.empty:
                        print(f"📭 Нет данных для куратора '{curator_name}' за последние {days} дней")
                        return
                    
                    total_chats = df['chats_count'].sum()
                    avg_chats = df['chats_count'].mean()
                    
                    print(f"📊 Статистика куратора '{curator_name}' за {days} дней:")
                    print(f"💬 Всего чатов: {total_chats}")
                    print(f"📈 Среднее в час: {avg_chats:.1f}")
                    print("=" * 50)
                    
                    for _, row in df.iterrows():
                        print(f"📅 {row['message_date']} {row['message_hour']:02d}:00 | 💬 {row['chats_count']} чатов")
                else:
                    # Топ кураторов
                    query = """
                    SELECT curator_name, SUM(chats_count) as total_chats, COUNT(*) as records
                    FROM curator_messages
                    WHERE message_date >= date('now', '-{} days')
                    GROUP BY curator_name
                    ORDER BY total_chats DESC
                    LIMIT 10
                    """.format(days)
                    df = pd.read_sql_query(query, conn)
                    
                    if df.empty:
                        print(f"📭 Нет данных за последние {days} дней")
                        return
                    
                    print(f"🏆 Топ кураторов за {days} дней:")
                    print("=" * 60)
                    for i, (_, row) in enumerate(df.iterrows(), 1):
                        print(f"{i:2d}. {row['curator_name']:20} | 💬 {row['total_chats']:4d} чатов | 📝 {row['records']:2d} записей")
                    print("=" * 60)
                    
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
    
    def export_to_csv(self, filename: str = None) -> None:
        """Экспортирует данные в CSV файл"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT curator_name, discord_id, message_date, message_hour, chats_count, created_at
                FROM curator_messages
                ORDER BY created_at DESC
                """
                df = pd.read_sql_query(query, conn)
                
                if df.empty:
                    print("📭 Нет данных для экспорта")
                    return
                
                output_filename = filename or f"bot_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                df.to_csv(output_filename, index=False, encoding='utf-8')
                print(f"✅ Данные экспортированы в {output_filename}")
                print(f"📊 Экспортировано {len(df)} записей")
                
        except Exception as e:
            print(f"❌ Ошибка экспорта: {e}")
    
    def export_to_json(self, filename: str = None) -> None:
        """Экспортирует данные в JSON файл"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT curator_name, discord_id, message_date, message_hour, chats_count, created_at
                FROM curator_messages
                ORDER BY created_at DESC
                """
                df = pd.read_sql_query(query, conn)
                
                if df.empty:
                    print("📭 Нет данных для экспорта")
                    return
                
                output_filename = filename or f"bot_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                # Конвертируем в JSON
                data = df.to_dict('records')
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"✅ Данные экспортированы в {output_filename}")
                print(f"📊 Экспортировано {len(data)} записей")
                
        except Exception as e:
            print(f"❌ Ошибка экспорта: {e}")
    
    def get_daily_summary(self, date: str = None) -> None:
        """Показывает сводку за день"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if not date:
                    date = datetime.now().strftime('%Y-%m-%d')
                
                query = """
                SELECT curator_name, message_hour, chats_count
                FROM curator_messages
                WHERE message_date = ?
                ORDER BY message_hour, curator_name
                """
                df = pd.read_sql_query(query, conn, params=(date,))
                
                if df.empty:
                    print(f"📭 Нет данных за {date}")
                    return
                
                print(f"📅 Сводка за {date}:")
                print("=" * 60)
                
                # Группируем по часам
                for hour in sorted(df['message_hour'].unique()):
                    hour_data = df[df['message_hour'] == hour]
                    total_chats = hour_data['chats_count'].sum()
                    curators = len(hour_data)
                    
                    print(f"🕐 {hour:02d}:00 | 💬 {total_chats:3d} чатов | 👥 {curators} кураторов")
                    for _, row in hour_data.iterrows():
                        print(f"    👤 {row['curator_name']}: {row['chats_count']} чатов")
                    print()
                
                print("=" * 60)
                print(f"📊 Итого за день: {df['chats_count'].sum()} чатов от {len(df['curator_name'].unique())} кураторов")
                
        except Exception as e:
            print(f"❌ Ошибка получения сводки: {e}")

def main():
    parser = argparse.ArgumentParser(description="Анализатор базы данных Discord бота")
    parser.add_argument("--db", default="bot_database.db", help="Путь к файлу базы данных")
    parser.add_argument("--action", choices=["info", "recent", "stats", "curator", "export-csv", "export-json", "daily"], 
                       default="info", help="Действие для выполнения")
    parser.add_argument("--limit", type=int, default=10, help="Количество записей для показа")
    parser.add_argument("--days", type=int, default=7, help="Количество дней для анализа")
    parser.add_argument("--curator", help="Имя куратора для анализа")
    parser.add_argument("--date", help="Дата для сводки (YYYY-MM-DD)")
    parser.add_argument("--output", help="Имя файла для экспорта")
    
    args = parser.parse_args()
    
    analyzer = DatabaseAnalyzer(args.db)
    
    if not analyzer.check_connection():
        sys.exit(1)
    
    if args.action == "info":
        info = analyzer.get_database_info()
        if info:
            print("📊 Информация о базе данных:")
            print(f"📝 Всего записей: {info['total_records']}")
            print(f"👥 Уникальных кураторов: {info['unique_curators']}")
            print(f"📅 Период: {info['date_range'][0]} - {info['date_range'][1]}")
            print(f"💬 Общее количество чатов: {info['total_chats']}")
    
    elif args.action == "recent":
        analyzer.show_recent_data(args.limit)
    
    elif args.action == "stats":
        analyzer.get_curator_stats(days=args.days)
    
    elif args.action == "curator":
        if not args.curator:
            print("❌ Укажите имя куратора с помощью --curator")
            sys.exit(1)
        analyzer.get_curator_stats(args.curator, args.days)
    
    elif args.action == "export-csv":
        analyzer.export_to_csv(args.output)
    
    elif args.action == "export-json":
        analyzer.export_to_json(args.output)
    
    elif args.action == "daily":
        analyzer.get_daily_summary(args.date)

if __name__ == "__main__":
    main() 