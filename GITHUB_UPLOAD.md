# 📤 Загрузка проекта на GitHub

## 🚀 Быстрый старт

### 1. Создание репозитория на GitHub

1. Перейдите на [GitHub](https://github.com/new)
2. Заполните форму:
   - **Repository name**: `discord-bot-v2`
   - **Description**: `Discord Bot v2 - Система учета кураторов с Docker и аналитикой`
   - **Visibility**: Public или Private (на ваш выбор)
   - **НЕ ставьте галочки** на "Add a README file", "Add .gitignore", "Choose a license"

3. Нажмите "Create repository"

### 2. Загрузка кода

После создания репозитория выполните команды:

```bash
# Добавить remote origin (замените YOUR_USERNAME на ваше имя пользователя)
git remote add origin https://github.com/YOUR_USERNAME/discord-bot-v2.git

# Переименовать ветку в main
git branch -M main

# Загрузить код
git push -u origin main
```

### 3. Автоматическая загрузка

Или используйте наш скрипт:

```bash
./upload_to_github.sh
```

## 🔧 Настройка SSH (опционально)

Если у вас настроен SSH ключ, используйте SSH URL:

```bash
git remote add origin git@github.com:YOUR_USERNAME/discord-bot-v2.git
git branch -M main
git push -u origin main
```

## 📋 Что будет загружено

- ✅ **Основной код бота** - все Python файлы
- ✅ **Docker конфигурация** - Dockerfile, docker-compose.yml
- ✅ **Скрипты управления** - manage.sh, analyze.sh, run.sh
- ✅ **Документация** - README.md, инструкции
- ✅ **Конфигурация** - requirements.txt, .gitignore

## 🚫 Что НЕ будет загружено

- ❌ **Конфиденциальные данные** - .env, credentials.json
- ❌ **База данных** - bot_database.db
- ❌ **Логи** - bot.log
- ❌ **Кэш Python** - __pycache__/

## 🔄 Обновление кода

После внесения изменений:

```bash
# Добавить изменения
git add .

# Создать коммит
git commit -m "Описание изменений"

# Загрузить на GitHub
git push
```

## 🌟 После загрузки

1. **Добавьте описание** в репозиторий
2. **Настройте теги** для версий
3. **Создайте Issues** для багов и предложений
4. **Добавьте Wiki** с дополнительной документацией

## 📝 Примеры коммитов

```bash
git commit -m "feat: добавить новую команду !статистика"
git commit -m "fix: исправить ошибку в логировании"
git commit -m "docs: обновить README.md"
git commit -m "refactor: улучшить структуру кода"
```

## 🎯 Готово!

После загрузки ваш проект будет доступен по адресу:
`https://github.com/YOUR_USERNAME/discord-bot-v2`

Теперь другие разработчики смогут:
- Клонировать ваш репозиторий
- Использовать ваш код
- Предлагать улучшения через Pull Requests
- Сообщать о багах через Issues 