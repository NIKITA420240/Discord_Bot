import re
from datetime import datetime, timedelta, timezone
# УБРАЛИ: from users import user_map
import logging
from utils import Time_to_send, Default_curator, months_name
from database import DatabaseManager

class DataCollector:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.black_users = set()
    
    def get_curator_chats(self, message):
        """Извлекает количество чатов из сообщения и определяет время"""
        if (message.created_at.minute < Time_to_send):
            msg_time = message.created_at + timedelta(hours=2)
        else:
            msg_time = message.created_at + timedelta(hours=3)
        
        day = msg_time.day
        month_name = months_name[msg_time.month - 1]
        hour = msg_time.hour
        message_date = msg_time.strftime('%Y-%m-%d')

        if message.content.lower().strip() == "c" or message.content.lower().strip() == "с":
            return -1, day, month_name, hour, message_date, msg_time
            
        numbers = re.findall(r'\d+', message.content.strip())
        if numbers:
            total = sum(map(int, numbers))
            return total, day, month_name, hour, message_date, msg_time
            
        return 0, day, month_name, hour, message_date, msg_time

    async def collect_discord_data(self, channel):
        """Собирает сообщения пользователей за последний час с сохранением в БД"""
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        curator_data = {}
        seen_users = set()

        day = month_name = hour = message_date = None
        dt_object = datetime.now() 

        async for message in channel.history(limit=1000):
            if message.author.bot:
                if message.content.startswith("Пишите количество чатов за"):
                    break
                continue
            if message.created_at < one_hour_ago:
                break
                
            author_tag = str(message.author) # ds_id куратора (username)
            if author_tag in seen_users:
                continue
            
            # --- ИЗМЕНЕНИЕ: БЕРЕМ ИЗ БД ---
            name = self.db_manager.get_user_name(author_tag)

            # Если не нашли в БД
            if not name:
                if name not in self.black_users:
                    warning_msg = f"Пользователь {message.author.mention} ({author_tag}) не найден в базе кураторов!"
                    await channel.send(warning_msg)
                    logging.info(f"Пользователь {author_tag} не является куратором")
                    self.black_users.add(author_tag)

                # Записываем как Дефолтного
                total, day, month_name, hour, message_date, msg_time = self.get_curator_chats(message)
                curator_data[Default_curator] = total
                seen_users.add(author_tag)
                dt_object = msg_time 
                
                self.db_manager.add_curator_message(
                    Default_curator, 
                    author_tag, 
                    message_date, 
                    hour, 
                    total
                )
                continue
            
            # Если нашли
            total, day, month_name, hour, message_date, msg_time = self.get_curator_chats(message)
            curator_data[name] = total
            seen_users.add(author_tag)
            dt_object = msg_time 
            
            self.db_manager.add_curator_message(
                str(name), 
                author_tag, 
                message_date, 
                hour, 
                total
            )
            logging.info(f"Считали - {name} [{day} {month_name}] [{hour}:00]: {total} чатов")
            
        return curator_data, hour, day, month_name, dt_object
    
    # Методы-прокси оставляем без изменений
    def get_stats_from_db(self, message_date: str, message_hour: int):
        return self.db_manager.get_curator_stats_for_hour(message_date, message_hour)
    def get_curator_history(self, curator_name: str, days: int = 7):
        return self.db_manager.get_curator_history(curator_name, days)
    def get_daily_stats(self, date: str):
        return self.db_manager.get_daily_stats(date)
    def get_top_curators_count_hours(self, days: int = 7, limit: int = 10):
        return self.db_manager.get_top_curators_count_hours(days, limit) 
    def get_top_curators_count_sms(self, days: int = 7, limit: int = 10):
        return self.db_manager.get_top_curators_count_sms(days, limit)