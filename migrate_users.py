from database import DatabaseManager
from users import user_map

def migrate():
    print("🚀 Начинаем миграцию пользователей в базу данных...")
    
    # Инициализируем БД (создаст таблицу users, если нет)
    db = DatabaseManager("bot_database.db")
    
    count = 0
    for discord_id, name in user_map.items():
        if db.add_user(discord_id, name):
            print(f"✅ Добавлен: {discord_id} -> {name}")
            count += 1
        else:
            print(f"❌ Ошибка добавления: {discord_id}")
            
    print(f"\n🎉 Миграция завершена! Перенесено {count} пользователей.")

if __name__ == "__main__":
    migrate()