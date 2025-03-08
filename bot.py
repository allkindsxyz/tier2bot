import logging
import openai
import asyncio
from openai import OpenAI
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
from telegram.constants import ParseMode
import psutil
import sys
import os
import time
import signal
import random
from questions import ALL_QUESTIONS  # Импортируем вопросы из отдельного модуля
import json
from typing import Dict, Any
import sqlite3
from datetime import datetime
from pathlib import Path
import shutil
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем значения из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
BOT_USERNAME = os.getenv('BOT_USERNAME')
CALENDLY_LINK = os.getenv('CALENDLY_LINK')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'tier2botadmin')

# Создаем структуру директорий для данных
BASE_DIR = Path(__file__).resolve().parent  # Директория с bot.py
DATA_DIR = BASE_DIR / "data"  # Директория для всех данных
DB_DIR = DATA_DIR / "db"  # Директория для баз данных
LOGS_DIR = DATA_DIR / "logs"  # Директория для логов
TEMP_DIR = DATA_DIR / "temp"  # Директория для временных файлов

# Создаем необходимые директории
for dir_path in [DATA_DIR, DB_DIR, LOGS_DIR, TEMP_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Определяем пути к файлам
DATABASE_FILE = DB_DIR / "test_results.db"
PROGRESS_FILE = TEMP_DIR / "user_progress.json"
LOG_FILE = LOGS_DIR / "bot.log"

# Настраиваем логирование с новым путем к файлу
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Определяем состояния
WAITING_FOR_INITIAL_CHOICE = 0
WAITING_FOR_BENEFITS_CHOICE = 1
WAITING_FOR_TEST_CHOICE = 2
WAITING_FOR_CONTINUE_CHOICE = 3
ANSWERING_QUESTIONS = 4
WAITING_FOR_SECOND_TEST = 5  # Новое состояние для ожидания результатов второго теста
WAITING_FOR_ADMIN_RESPONSE = 6

# Создаём клиента OpenAI
client = OpenAI()

def init_database():
    """
    Инициализирует базу данных
    """

    try:
        pass
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {e}")

def save_answer_to_db(user_id: int, question_number: int, answer: str):
    """
    Сохраняет каждый ответ пользователя в базу данных
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Создаем таблицу, если она не существует
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS answers (
                user_id INTEGER,
                question_number INTEGER,
                answer TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Сохраняем ответ
        cursor.execute(
            'INSERT INTO answers (user_id, question_number, answer) VALUES (?, ?, ?)',
            (user_id, question_number, answer)
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка при сохранении ответа в базу данных: {e}")

def save_test_results(user_id: int, username: str, first_name: str, answers: list, answer_stats: dict):
    """
    Сохраняет результаты теста в базу данных
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Создаем таблицу, если она не существует
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                answers TEXT,
                answer_stats TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Сохраняем результаты
        cursor.execute(
            'INSERT INTO test_results (user_id, username, first_name, answers, answer_stats) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, first_name, json.dumps(answers), json.dumps(answer_stats))
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Ошибка при сохранении результатов теста в базу данных: {e}")

def update_test_status(user_id: int, status: str):
    """
    Обновляет статус теста пользователя
    """

    try:
        pass
    except Exception as e:
        logging.error(f"Ошибка при обновлении статуса теста пользователя: {e}")

def save_user_progress(user_id: int, data: Dict[str, Any]) -> None:
    """
    Сохраняет прогресс пользователя в файл
    """
    try:
        # Загружаем существующие данные
        all_progress = {}
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                all_progress = json.load(f)
        
        # Обновляем данные для конкретного пользователя
        all_progress[str(user_id)] = data
        
        # Сохраняем обновленные данные
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(all_progress, f)
    except Exception as e:
        logging.error(f"Ошибка при сохранении прогресса пользователя в файл: {e}")

def load_user_progress(user_id: int) -> Dict[str, Any]:
    """
    Загружает прогресс пользователя из файла
    """
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                all_progress = json.load(f)
                return all_progress.get(str(user_id), {})
        return {}
    except Exception as e:
        logging.error(f"Ошибка при загрузке прогресса пользователя из файла: {e}")
        return {}

def clear_user_progress(user_id: int) -> None:
    """
    Очищает сохраненный прогресс пользователя
    """
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                all_progress = json.load(f)
            
            # Удаляем данные пользователя, если они есть
            all_progress.pop(str(user_id), None)
            
            with open(PROGRESS_FILE, 'w') as f:
                json.dump(all_progress, f)
    except Exception as e:
        logging.error(f"Ошибка при очистке сохраненного прогресса пользователя: {e}")

def format_question_with_options(question: dict, question_number: int) -> tuple[str, dict, list]:
    """
    Форматирует вопрос и варианты ответов, возвращает текст и маппинг случайных ответов
    """
    total_questions = len(ALL_QUESTIONS)
    options = question["options"]
    
    # Создаем список пар (номер, текст ответа)
    original_options = [(str(i), options[str(i)]) for i in range(1, 5)]
    
    # Перемешиваем варианты ответов
    random.shuffle(original_options)
    
    # Создаем маппинг буква -> номер ответа для подсчета статистики
    letter_to_number = {
        'A': original_options[0][0],
        'B': original_options[1][0],
        'C': original_options[2][0],
        'D': original_options[3][0]
    }
    
    # Форматируем текст вопроса
    question_text = question['question'].replace("*Вопрос:*\n", "")
    formatted_text = (
        f"*Вопрос {question_number + 1} из {total_questions}:* {question_text}\n\n"
    )
    
    # Добавляем варианты ответов в фиксированном порядке A, B, C, D
    letters = ['A', 'B', 'C', 'D']
    for i, letter in enumerate(letters):
        text = original_options[i][1]
        formatted_text += f"{letter}\\. {escape_markdown_v2(text)}\n\n"
    
    # Создаем список букв для клавиатуры в фиксированном порядке
    keyboard_letters = ['A', 'B', 'C', 'D']
    
    return formatted_text, letter_to_number, keyboard_letters

async def start(update: Update, context: CallbackContext) -> int:
    """
    Отправляет приветственное сообщение и показывает меню
    """
    logging.info(f"Получена команда /start от пользователя {update.message.from_user.id}")
    
    keyboard = [
        ["Да, пожалуйста", "Нет, спасибо"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Привет! Хотите узнать, какие преимущества даёт переход на Тиер 2?",
        reply_markup=reply_markup
    )
    
    return WAITING_FOR_BENEFITS_CHOICE

async def handle_benefits_choice(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает выбор пользователя о просмотре преимуществ
    """
    choice = update.message.text
    logging.info(f"Получен ответ от пользователя: {choice}")
    
    if choice == "Да, пожалуйста":
        logging.info("Пользователь выбрал 'Да, пожалуйста'")
        benefits_message = (
            "*Что даёт переход на Тиер 2:*\n\n"
            "1\\. Ясность мышления \\- вы начинаете видеть ситуации с разных сторон\n\n"
            "2\\. Гибкость \\- вы легко адаптируетесь к изменениям\n\n"
            "3\\. Принятие неопределенности \\- вы не боитесь неизвестного\n\n"
            "4\\. Эмоциональная зрелость \\- вы управляете своими реакциями\n\n"
            "5\\. Глубокие отношения \\- вы строите настоящие связи\n\n"
            "6\\. Осознанные решения \\- вы делаете выбор на основе понимания\n\n"
            "7\\. Внутренняя свобода \\- вы не зависите от мнения других\n\n"
            "8\\. Системное мышление \\- вы видите взаимосвязи\n\n"
            "9\\. Личностный рост \\- вы постоянно развиваетесь\n\n"
            "_Это не просто новый уровень мышления \\- это более осознанная и наполненная жизнь_"
        )
        
        keyboard = [
            ["📝 Пройти тест", "Нет, спасибо"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            benefits_message + "\n\nДля участия в программе вам надо пройти два теста\\. Начать первый?",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
        return WAITING_FOR_TEST_CHOICE
    else:
        await update.message.reply_text(
            "Спасибо за интерес! Если захотите узнать больше, просто нажмите /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def start_test(update: Update, context: CallbackContext) -> int:
    """
    Начинает тест
    """
    choice = update.message.text
    user_id = update.message.from_user.id
    
    if choice == "📝 Пройти тест":
        # Очищаем прогресс пользователя перед началом теста
        clear_user_progress(user_id)
        
        # Загружаем первый вопрос
        current_question = 0
        question = ALL_QUESTIONS[current_question]
        
        # Форматируем вопрос и получаем маппинг ответов
        formatted_text, letter_to_number, keyboard_letters = format_question_with_options(question, current_question)
        
        # Создаем клавиатуру с буквами ответов по 2 в ряд
        keyboard = [keyboard_letters[i:i+2] for i in range(0, 4, 2)]
        keyboard.append(["Отменить"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Сохраняем начальное состояние с маппингом
        save_user_progress(user_id, {
            "current_question": 0,
            "answers": [],
            "answer_stats": {"1": 0, "2": 0, "3": 0, "4": 0},
            "current_mapping": letter_to_number
        })
        
        # Отправляем первый вопрос
        await update.message.reply_text(
            formatted_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
        return ANSWERING_QUESTIONS
    else:
        await update.message.reply_text(
            "Спасибо за интерес! Если захотите пройти тест позже, просто нажмите /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def start_new_test(update: Update, context: CallbackContext) -> str:
    """
    Начинает новый тест
    """

    user_id = update.message.from_user.id

async def handle_continue_choice(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает выбор пользователя о продолжении теста
    """
    choice = update.message.text
    user_id = update.message.from_user.id

    if choice == "Продолжить":
        # Загружаем прогресс пользователя
        progress = load_user_progress(user_id)
        current_question = progress.get("current_question", 0)
        
        if current_question >= len(ALL_QUESTIONS):
            # Если все вопросы закончились, завершаем тест
            return await finish_test(update, context)
        
        # Получаем текущий вопрос
        question = ALL_QUESTIONS[current_question]
        
        # Создаем клавиатуру с вариантами ответов
        keyboard = [[answer] for answer in question["answers"]]
        keyboard.append(["Отменить"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем вопрос пользователю
        await update.message.reply_text(
            f"{current_question + 1}. {question['text']}\n\n"
            "Выберите один из вариантов:",
            reply_markup=reply_markup
        )
        return ANSWERING_QUESTIONS
    else:
        await update.message.reply_text(
            "Тест отменен. Для начала нажмите /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def handle_answer(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает ответ пользователя на вопрос
    """
    answer = update.message.text
    user_id = update.message.from_user.id

    if answer == "Отменить":
        await update.message.reply_text(
            "Тест отменен. Для начала нажмите /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    # Загружаем прогресс пользователя
    progress = load_user_progress(user_id)
    current_question = progress.get("current_question", 0)
    answers = progress.get("answers", [])
    answer_stats = progress.get("answer_stats", {"1": 0, "2": 0, "3": 0, "4": 0})
    letter_to_number = progress.get("current_mapping", {})

    # Преобразуем букву ответа в номер и сохраняем
    original_answer_number = letter_to_number.get(answer)
    if original_answer_number:
        answer_stats[original_answer_number] += 1
        answers.append(original_answer_number)

        # Сохраняем ответ в базу данных
        save_answer_to_db(user_id, current_question, original_answer_number)
        
        # Сохраняем обновленный прогресс
        current_question += 1
        save_user_progress(user_id, {
            "current_question": current_question,
            "answers": answers,
            "answer_stats": answer_stats,
            "current_mapping": letter_to_number
        })

    if current_question >= len(ALL_QUESTIONS):
        # Если все вопросы закончились, сохраняем результаты
        save_test_results(
            user_id,
            update.message.from_user.username or "",
            update.message.from_user.first_name or "",
            answers,
            answer_stats
        )
        return await finish_test(update, context)
    else:
        # Получаем следующий вопрос
        question = ALL_QUESTIONS[current_question]
        
        # Форматируем следующий вопрос и получаем новый маппинг
        formatted_text, letter_to_number, keyboard_letters = format_question_with_options(question, current_question)
        
        # Создаем клавиатуру с буквами ответов по 2 в ряд
        keyboard = [keyboard_letters[i:i+2] for i in range(0, 4, 2)]
        keyboard.append(["Отменить"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Сохраняем прогресс с новым маппингом
        save_user_progress(user_id, {
            "current_question": current_question,
            "answers": answers,
            "answer_stats": answer_stats,
            "current_mapping": letter_to_number
        })
        
        # Отправляем следующий вопрос
        await update.message.reply_text(
            formatted_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
        return ANSWERING_QUESTIONS

async def handle_admin_response(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает ответ администратора на результаты теста
    """
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    try:
        # Разбираем команду /respond user_id status
        _, user_id, status = update.message.text.split()
        user_id = int(user_id)
        
        if status.lower() == "принят":
            message = (
                "🎊 *Поздравляем! Вы приняты в программу Welcome to Tier 2!*\n\n"
                "Для начала работы и согласования расписания, пожалуйста, запишитесь на вводную встречу:\n"
                f"{CALENDLY_LINK}"
            )
        elif status.lower() == "отклонен":
            message = (
                "*Спасибо за интерес к нашей программе!*\n\n"
                "К сожалению, на данном этапе мы не можем предложить вам участие в программе.\n"
                "Рекомендуем продолжить работу над собой и попробовать снова через некоторое время."
            )
        else:
            await update.message.reply_text("Неверный статус. Используйте 'Принят' или 'Отклонен'.")
            return

        # Пытаемся отправить сообщение пользователю
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            await update.message.reply_text(
                f"✅ Ответ успешно отправлен пользователю (ID: {user_id})"
            )
        except Exception as e:
            if "bot can't initiate conversation with a user" in str(e):
                await update.message.reply_text(
                    f"❌ Не удалось отправить ответ пользователю. Он еще не начал диалог с ботом.\n\n"
                    f"*Необходимые действия:*\n"
                    f"1. Попросите пользователя перейти в @{BOT_USERNAME}\n"
                    f"2. Нажать START или отправить команду /start\n"
                    f"3. После этого повторите отправку ответа той же командой",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(f"❌ Ошибка при отправке ответа: {str(e)}")

    except ValueError:
        await update.message.reply_text(
            "Неверный формат команды. Используйте:\n"
            "`/respond user_id Принят`\n"
            "или\n"
            "`/respond user_id Отклонен`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке ответа: {str(e)}")

async def test_message(update: Update, context: CallbackContext) -> None:
    """
    Тестовая команда для проверки отправки сообщений администратору
    """

    try:
        logging.info(f"Тестовая отправка сообщения администратору (ID: {ADMIN_ID})")
    except Exception as e:
        logging.error(f"Ошибка при отправке тестового сообщения: {str(e)}")

async def handle_admin_decision(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает решение администратора через кнопки
    """
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    try:
        decision_text = update.message.text
        if not (decision_text.startswith("Принять ") or decision_text.startswith("Отклонить ")):
            return

        # Извлекаем user_id из текста кнопки
        user_id = int(decision_text.split()[1])
        status = "Принят" if decision_text.startswith("Принять") else "Отклонен"
        
        if status == "Принят":
            message = (
                "🎊 *Поздравляем\\! Вы приняты в программу Welcome to Tier 2\\!*\n\n"
                "Для начала работы и согласования расписания, пожалуйста, запишитесь на вводную встречу:\n"
                f"{escape_markdown_v2(CALENDLY_LINK)}"
            )
        else:
            message = (
                "*Спасибо за интерес к нашей программе\\!*\n\n"
                "К сожалению, на данном этапе мы не можем предложить вам участие в программе\\.\n"
                "Рекомендуем продолжить работу над собой и попробовать снова через некоторое время\\."
            )

        # Отправляем сообщение пользователю
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            await update.message.reply_text(
                f"✅ Ответ успешно отправлен пользователю (ID: {user_id})",
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            if "bot can't initiate conversation with a user" in str(e):
                await update.message.reply_text(
                    f"❌ Не удалось отправить ответ пользователю\\. Он еще не начал диалог с ботом\\.\n\n"
                    f"*Необходимые действия:*\n"
                    f"1\\. Попросите пользователя перейти в @{BOT_USERNAME}\n"
                    f"2\\. Нажать START или отправить команду /start\n"
                    f"3\\. После этого повторите отправку ответа той же командой",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await update.message.reply_text(f"❌ Ошибка при отправке ответа: {str(e)}")

    except Exception as e:
        logging.error(f"Ошибка при обработке решения администратора: {e}")
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")

def escape_markdown_v2(text):
    """
    Экранирует специальные символы для Markdown V2
    """

    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def finish_test(update: Update, context: CallbackContext) -> int:
    """
    Завершает тест и предлагает пройти второй тест
    """
    try:
        user_id = update.message.from_user.id
        
        # Формируем сообщение с результатами
        results_message = (
            "*Спасибо за прохождение первого теста\\!*\n\n"
            "Для полной оценки вашего уровня, пожалуйста, пройдите второй тест по ссылке:\n"
            "[Пройти второй тест](https://sdtest\\.me/ru)\n\n"
            "После прохождения теста, пожалуйста, *сделайте скриншот результатов* "
            "и отправьте его сюда\\."
        )
        
        keyboard = [["Отменить"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            results_message,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        
        return WAITING_FOR_SECOND_TEST
        
    except Exception as e:
        logging.error(f"Ошибка при завершении теста: {str(e)}")
        return ConversationHandler.END

async def handle_second_test_results(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает получение скриншота со вторым тестом
    """
    try:
        if not update.message.photo:
            await update.message.reply_text(
                "Пожалуйста, отправьте скриншот с результатами второго теста.",
                reply_markup=ReplyKeyboardMarkup([["Отменить"]], resize_keyboard=True)
            )
            return WAITING_FOR_SECOND_TEST

        user_id = update.message.from_user.id
        photo = update.message.photo[-1]  # Берем самую большую версию фото
        
        # Загружаем результаты первого теста и обновляем статистику последнего ответа
        progress = load_user_progress(user_id)
        answers = progress.get("answers", [])
        answer_stats = progress.get("answer_stats", {"1": 0, "2": 0, "3": 0, "4": 0})
        letter_to_number = progress.get("current_mapping", {})
        
        # Сохраняем обновленную статистику
        save_user_progress(user_id, {
            "current_question": len(answers),
            "answers": answers,
            "answer_stats": answer_stats,
            "current_mapping": letter_to_number
        })

        # Отправляем уведомление администратору с результатами обоих тестов
        admin_message = (
            f"📊 Новые результаты тестов!\n\n"
            f"Пользователь: {update.message.from_user.first_name}"
            f" (@{update.message.from_user.username})\n"
            f"ID: {user_id}\n\n"
            f"Результаты первого теста:\n"
            f"1: {answer_stats['1']}\n"
            f"2: {answer_stats['2']}\n"
            f"3: {answer_stats['3']}\n"
            f"4: {answer_stats['4']}\n\n"
            f"Скриншот второго теста прикреплен выше."
        )

        # Создаем клавиатуру с кнопками для администратора
        admin_keyboard = [
            [f"Принять {user_id}", f"Отклонить {user_id}"]
        ]
        admin_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)

        try:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo.file_id,
                caption=admin_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=admin_markup
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке скриншота администратору: {str(e)}")

        # Отправляем сообщение пользователю
        await update.message.reply_text(
            "Спасибо! Ваши результаты получены и отправлены на рассмотрение.\n"
            "Мы свяжемся с вами в ближайшее время.",
            reply_markup=ReplyKeyboardRemove()
        )

        return ConversationHandler.END

    except Exception as e:
        logging.error(f"Ошибка при обработке результатов теста: {str(e)}")
        return WAITING_FOR_SECOND_TEST

async def cancel(update: Update, context: CallbackContext) -> int:
    """
    Отменяет текущий диалог
    """

    try:
        await update.message.reply_text(
            "Тест отменен. Для начала нажмите /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Ошибка при отмене диалога: {str(e)}")
        return ConversationHandler.END

def create_backup():
    """
    Создает резервную копию базы данных
    """

    try:
        logging.info("Создание резервной копии базы данных")
    except Exception as e:
        logging.error(f"Ошибка при создании резервной копии: {str(e)}")

def schedule_backup():
    """
    Планирует регулярное создание бэкапов
    """

    try:
        logging.info("Планирование резервного копирования")
    except Exception as e:
        logging.error(f"Ошибка при планировании резервного копирования: {str(e)}")

def main() -> None:
    """
    Запускает Telegram-бота
    """

    try:
        logging.info("Запуск бота")
        
        # Создаем приложение с увеличенным таймаутом
        application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .connect_timeout(30.0)  # Увеличиваем таймаут соединения до 30 секунд
            .read_timeout(30.0)     # Увеличиваем таймаут чтения до 30 секунд
            .write_timeout(30.0)    # Увеличиваем таймаут записи до 30 секунд
            .build()
        )

        # Создаем обработчик диалога
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                WAITING_FOR_INITIAL_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_benefits_choice)],
                WAITING_FOR_BENEFITS_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_benefits_choice)],
                WAITING_FOR_TEST_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_test)],
                ANSWERING_QUESTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)],
                WAITING_FOR_SECOND_TEST: [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_second_test_results)],
                WAITING_FOR_ADMIN_RESPONSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_response)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )

        # Добавляем обработчики
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("respond", handle_admin_response))
        application.add_handler(CommandHandler("test", test_message))
        
        # Добавляем обработчик для кнопок администратора
        application.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r"^(Принять|Отклонить) \d+$"),
            handle_admin_decision
        ))

        # Добавляем обработчик ошибок с более информативными сообщениями
        async def error_handler(update: object, context: CallbackContext) -> None:
            error_message = str(context.error)
            logging.error(f"Произошла ошибка: {error_message}")
            
            user_message = "Извините, произошла ошибка. "
            if "Timed out" in error_message:
                user_message += "Превышено время ожидания ответа. Пожалуйста, повторите попытку."
            elif "NetworkError" in error_message:
                user_message += "Проблема с сетевым подключением. Пожалуйста, проверьте ваше соединение."
            else:
                user_message += "Пожалуйста, попробуйте позже или начните сначала с помощью /start"
            
            if update and isinstance(update, Update) and update.effective_message:
                try:
                    await update.effective_message.reply_text(user_message)
                except Exception as e:
                    logging.error(f"Не удалось отправить сообщение об ошибке: {e}")

        application.add_error_handler(error_handler)

        # Запускаем бота с настройками повторных попыток
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Игнорируем обновления, накопившиеся во время простоя
            pool_timeout=30.0,          # Увеличиваем таймаут пула
            read_timeout=30.0,          # Увеличиваем таймаут чтения
            write_timeout=30.0          # Увеличиваем таймаут записи
        )
        
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
    finally:
        logging.info("Завершение работы бота...")