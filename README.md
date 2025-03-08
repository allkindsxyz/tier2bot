# EnterTier2Bot

Telegram-бот для проведения тестирования и оценки готовности к переходу на Tier 2.

## Функциональность

- Информирование о преимуществах перехода на Tier 2
- Проведение первичного теста
- Сбор результатов второго теста (скриншот)
- Административный интерфейс для принятия решений
- Сохранение результатов тестирования в базе данных

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/EnterTier2Bot.git
cd EnterTier2Bot
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate  # Для Linux/Mac
# или
venv\Scripts\activate  # Для Windows
pip install -r requirements.txt
```

3. Создайте файл `.env` с вашими настройками:
```env
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_ID=your_admin_id
BOT_USERNAME=your_bot_username
CALENDLY_LINK=your_calendly_link
```

## Запуск

```bash
python bot.py
```

## Структура проекта

- `bot.py` - основной файл бота
- `questions.py` - файл с вопросами для теста
- `data/` - директория для данных (создается автоматически)
  - `db/` - база данных SQLite
  - `logs/` - логи бота
  - `temp/` - временные файлы

## Требования

- Python 3.7+
- python-telegram-bot
- SQLite3
- Другие зависимости указаны в requirements.txt 