#!/bin/bash

# Скрипт для загрузки проекта на GitHub

echo "🚀 Загрузка проекта на GitHub"
echo "=============================="

# Проверяем, что мы в правильной директории
if [ ! -f "bot.py" ]; then
    echo "❌ Ошибка: файл bot.py не найден. Убедитесь, что вы в папке Bot-v2"
    exit 1
fi

# Проверяем статус Git
if [ ! -d ".git" ]; then
    echo "❌ Ошибка: Git репозиторий не инициализирован"
    exit 1
fi

echo "📋 Текущий статус Git:"
git status

echo ""
echo "🔗 Для загрузки на GitHub выполните следующие шаги:"
echo ""
echo "1. Создайте новый репозиторий на GitHub:"
echo "   - Перейдите на https://github.com/new"
echo "   - Название: discord-bot-v2"
echo "   - Описание: Discord Bot v2 - Система учета кураторов"
echo "   - Сделайте репозиторий публичным или приватным"
echo "   - НЕ инициализируйте с README, .gitignore или лицензией"
echo ""
echo "2. После создания репозитория выполните команды:"
echo ""
echo "   git remote add origin https://github.com/YOUR_USERNAME/discord-bot-v2.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. Или используйте SSH (если настроен):"
echo ""
echo "   git remote add origin git@github.com:YOUR_USERNAME/discord-bot-v2.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""

# Спрашиваем пользователя, хочет ли он продолжить
read -p "Хотите, чтобы я попытался автоматически загрузить на GitHub? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔍 Поиск существующих remote..."
    
    # Проверяем, есть ли уже remote origin
    if git remote get-url origin >/dev/null 2>&1; then
        echo "✅ Remote origin уже настроен:"
        git remote get-url origin
        echo ""
        echo "📤 Загружаем код на GitHub..."
        git branch -M main
        git push -u origin main
    else
        echo "❌ Remote origin не настроен"
        echo "Пожалуйста, создайте репозиторий на GitHub и выполните команды вручную"
    fi
else
    echo "✅ Хорошо! Выполните команды вручную после создания репозитория на GitHub"
fi

echo ""
echo "🎉 Готово! Ваш проект готов к загрузке на GitHub" 