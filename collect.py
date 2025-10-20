import re
from datetime import datetime, timedelta, timezone
from users import user_map
import logging
from utils import Time_to_send, Default_curator, months_name
from database import DatabaseManager

class DataCollector:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.black_users = set()
    
    def get_curator_chats(self, message):
        """Извлекает количество чатов из сообщения и определяет время"""
        # Время сообщения, если это 18:45 то количество чатов за 17, если 18:50 то за 18
        # Прибавляем поскольку считаем время относительно
        if (message.created_at.minute < Time_to_send):
            msg_time = message.created_at + timedelta(hours=2)
        else:
            msg_time = message.created_at + timedelta(hours=3)
        
        day = msg_time.day
        month_name = months_name[msg_time.month - 1]
        hour = msg_time.hour
        message_date = msg_time.strftime('%Y-%m-%d')

        # Учёт серого куратора
        if message.content == "c" or message.content == "с" or message.content == "С" or message.content == "C":
            return -1, day, month_name, hour, message_date
        numbers = re.findall(r'\d+', message.content.strip())
        if numbers:
            total = sum(map(int, numbers))
            return total, day, month_name, hour, message_date
        return 0, day, month_name, hour, message_date

    async def collect_discord_data(self, channel):
        """Собирает сообщения пользователей за последний час с сохранением в БД"""
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        curator_data = {}
        seen_users = set()

        day = month_name = hour = message_date = None

        async for message in channel.history(limit=1000):
            if message.author.bot:
                if message.content.startswith("Пишите количество чатов за"):
                    break
                continue
            if message.created_at < one_hour_ago:
                break
                
            author_tag = str(message.author) # ds_id куратора
            if author_tag in seen_users:
                continue  # Уже считан
            
            name = user_map.get(author_tag, -1) # Фамилия Имя куратора нашли

            if (name == -1) and (name not in self.black_users):
                # Отправляем сообщение в канал
                warning_msg = f"Пользователь {message.author.mention} не найден в базе кураторов!"
                await channel.send(warning_msg)
                
                # Логируем в консоль
                logging.info(f"Пользователь {author_tag} не является куратором")
                self.black_users.add(name)

                # Если неизвестный куратор - Егор Гаязов
                total, day, month_name, hour, message_date = self.get_curator_chats(message)
                curator_data[Default_curator] = total
                seen_users.add(author_tag)
                
                # Сохраняем в БД

                
                self.db_manager.add_curator_message(
                    Default_curator, 
                    author_tag, 
                    message_date, 
                    hour, 
                    total
                )
                
                logging.info(f"Считали Дефолтного куратора - {Default_curator} [{day} {month_name}] [{hour}:00]: {total} чатов")

                continue
            elif (name == -1):
                # Логируем в консоль
                logging.info(f"Пользователь {author_tag} не является куратором")

                # Если неизвестный куратор - Егор Гаязов
                total, day, month_name, hour, message_date = self.get_curator_chats(message)
                curator_data[Default_curator] = total
                seen_users.add(author_tag)
                
                # Сохраняем в БД
                self.db_manager.add_curator_message(
                    Default_curator, 
                    author_tag, 
                    message_date, 
                    hour, 
                    total
                )
                
                logging.info(f"Считали Дефолтного куратора - {Default_curator} [{day} {month_name}] [{hour}:00]: {total} чатов")
                continue
            
            total, day, month_name, hour, message_date = self.get_curator_chats(message)
            curator_data[name] = total
            seen_users.add(author_tag)
            
            # Сохраняем в БД
            self.db_manager.add_curator_message(
                str(name), 
                author_tag, 
                message_date, 
                hour, 
                total
            )
            
            logging.info(f"Считали - {name} [{day} {month_name}] [{hour}:00]: {total} чатов")
            
        return curator_data, hour, day, month_name, message_date

    def get_stats_from_db(self, message_date: str, message_hour: int):
        """Получает статистику из базы данных"""
        return self.db_manager.get_curator_stats_for_hour(message_date, message_hour)

    def get_curator_history(self, curator_name: str, days: int = 7):
        """Получает историю куратора из БД"""
        return self.db_manager.get_curator_history(curator_name, days)

    def get_daily_stats(self, date: str):
        """Получает дневную статистику из БД"""
        return self.db_manager.get_daily_stats(date)

    def get_top_curators(self, days: int = 7, limit: int = 10):
        """Получает топ кураторов из БД"""
        return self.db_manager.get_top_curators(days, limit) 