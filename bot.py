import logging
import openai
import asyncio
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode
import psutil
import sys
import os
import time
import signal
import random
from questions import ALL_QUESTIONS, get_questions_by_language  # Импортируем вопросы из отдельного модуля
import json
from typing import Dict, Any, Optional, List, Tuple
import sqlite3
from datetime import datetime
from pathlib import Path
import shutil
from dotenv import load_dotenv
import fcntl  # Для блокировки файла
import re
import schedule
import threading
from localization import get_text, save_user_language, get_user_language  # Импортируем функции для локализации

# Загружаем переменные окружения
load_dotenv()

# Получаем значения из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
BOT_USERNAME = os.getenv('BOT_USERNAME')
CALENDLY_LINK = os.getenv('CALENDLY_LINK')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'tier2botadmin')

# Создаем список администраторов
ADMIN_IDS = [ADMIN_ID]

# Создаем структуру директорий для данных
BASE_DIR = Path(__file__).resolve().parent  # Директория с bot.py
DATA_DIR = BASE_DIR / "data"  # Директория для всех данных
DB_DIR = DATA_DIR / "db"  # Директория для баз данных
LOGS_DIR = DATA_DIR / "logs"  # Директория для логов
TEMP_DIR = DATA_DIR / "temp"  # Директория для временных файлов
LOCK_FILE = DATA_DIR / "bot.lock"

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
CHOOSING_LANGUAGE = -1  # Новое состояние для выбора языка
WAITING_FOR_TEST_CHOICE = 2
WAITING_FOR_CONTINUE_CHOICE = 3
ANSWERING_QUESTIONS = 4
WAITING_FOR_SECOND_TEST = 5  # Новое состояние для ожидания результатов второго теста
WAITING_FOR_ADMIN_RESPONSE = 6

# Создаём клиента OpenAI
# client = OpenAI()

def check_single_instance():
    """
    Проверяет, что запущен только один экземпляр бота.
    Возвращает True, если это единственный экземпляр, иначе False.
    """
    global lock_file
    try:
        # Пытаемся создать и заблокировать файл
        lock_file = open(LOCK_FILE, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Записываем PID в файл блокировки
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        
        # Возвращаем True, если удалось получить блокировку
        return True
    except IOError:
        # Не удалось получить блокировку, значит другой экземпляр уже запущен
        logging.error("Другой экземпляр бота уже запущен. Завершение работы.")
        return False

def init_database():
    """
    Инициализирует базу данных
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Создаем таблицу для ответов пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS answers (
                user_id INTEGER,
                question_number INTEGER,
                answer TEXT,
                timestamp INTEGER,
                PRIMARY KEY (user_id, question_number)
            )
        ''')
        
        # Создаем таблицу для результатов тестов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                user_id INTEGER PRIMARY KEY,
                dominant_type TEXT,
                username TEXT,
                first_name TEXT,
                answers TEXT,
                answer_stats TEXT,
                timestamp INTEGER
            )
        ''')
        
        # Проверяем наличие столбца dominant_type в таблице test_results
        cursor.execute("PRAGMA table_info(test_results)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'dominant_type' not in columns:
            logging.info("Добавляем столбец dominant_type в таблицу test_results")
            cursor.execute("ALTER TABLE test_results ADD COLUMN dominant_type TEXT")
        
        # Проверяем наличие остальных столбцов в таблице test_results
        if 'username' not in columns:
            logging.info("Добавляем столбец username в таблицу test_results")
            cursor.execute("ALTER TABLE test_results ADD COLUMN username TEXT")
        
        if 'first_name' not in columns:
            logging.info("Добавляем столбец first_name в таблицу test_results")
            cursor.execute("ALTER TABLE test_results ADD COLUMN first_name TEXT")
        
        if 'answers' not in columns:
            logging.info("Добавляем столбец answers в таблицу test_results")
            cursor.execute("ALTER TABLE test_results ADD COLUMN answers TEXT")
        
        if 'answer_stats' not in columns:
            logging.info("Добавляем столбец answer_stats в таблицу test_results")
            cursor.execute("ALTER TABLE test_results ADD COLUMN answer_stats TEXT")
        
        # Создаем таблицу для полных результатов тестов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS full_test_results (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                answers TEXT,
                answer_stats TEXT,
                timestamp INTEGER
            )
        ''')
        
        # Создаем таблицу для статусов тестов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_status (
                user_id INTEGER PRIMARY KEY,
                status TEXT,
                timestamp INTEGER
            )
        ''')
        
        # Создаем таблицу для языковых настроек пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_language (
                user_id INTEGER PRIMARY KEY,
                language TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logging.info("База данных инициализирована успешно")
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {e}")

def get_db_connection():
    """
    Создает и возвращает соединение с базой данных
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        return conn
    except Exception as e:
        logging.error(f"Ошибка при подключении к базе данных: {e}")
        raise e

def save_answer_to_db(user_id: int, question_number: int, answer: str):
    """
    Сохраняет каждый ответ пользователя в базу данных
    """
    try:
        conn = get_db_connection()
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

def save_test_result(user_id: int, dominant_type: str):
    """
    Сохраняет результат теста пользователя (доминирующий тип)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT OR REPLACE INTO test_results (user_id, dominant_type, timestamp) VALUES (?, ?, ?)",
        (user_id, dominant_type, int(time.time()))
    )
    
    conn.commit()
    conn.close()

def save_test_results(user_id: int, username: str, first_name: str, answers: list, answer_stats: dict):
    """
    Сохраняет результаты теста в базу данных
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Проверяем, существует ли запись для этого пользователя
        cursor.execute('SELECT 1 FROM test_results WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Обновляем существующую запись
            cursor.execute(
                'UPDATE test_results SET username = ?, first_name = ?, answers = ?, answer_stats = ?, timestamp = CURRENT_TIMESTAMP WHERE user_id = ?',
                (username, first_name, json.dumps(answers), json.dumps(answer_stats), user_id)
            )
        else:
            # Создаем новую запись
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO test_status (user_id, status, timestamp) VALUES (?, ?, ?)",
            (user_id, status, int(time.time()))
        )
        
        conn.commit()
        conn.close()
        
        logging.info(f"Обновлен статус теста для пользователя {user_id}: {status}")
    except Exception as e:
        logging.error(f"Ошибка при обновлении статуса теста: {e}")

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
        logging.error(f"Ошибка при загрузке прогресса пользователя: {e}")
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

def format_question_with_options(question: dict, question_number: int, saved_options=None, user_id=None) -> tuple[str, dict, list]:
    """
    Форматирует вопрос с вариантами ответов для отображения
    """
    # Получаем язык пользователя (если не передан, используем русский)
    language = get_user_language(user_id) if user_id else "ru"
    
    # Получаем текст вопроса и варианты ответов
    question_text = question.get("question", "")
    # Удаляем префикс в зависимости от языка
    if language == "ru":
        question_text = question_text.replace("*Вопрос:*\n", "")
    else:
        question_text = question_text.replace("*Question:*\n", "")
    
    options = question.get("options", {})
    
    # Создаем список пар (номер, текст ответа)
    original_options = [(str(i), options.get(str(i), "")) for i in range(1, 5)]
    
    # Если есть сохраненный порядок вариантов, используем его
    # Иначе перемешиваем варианты ответов
    if saved_options:
        # Используем сохраненный порядок
        shuffled_options = saved_options
    else:
        # Перемешиваем варианты ответов
        shuffled_options = original_options.copy()
        random.shuffle(shuffled_options)
    
    # Создаем маппинг буква -> номер ответа для подсчета статистики
    letters = ["A", "B", "C", "D"]
    letter_to_number = {}
    keyboard_letters = []
    
    # Форматируем варианты ответов
    options_text = ""
    for i, (number, option_text) in enumerate(shuffled_options):
        letter = letters[i]
        keyboard_letters.append(letter)
        letter_to_number[letter] = number
        
        # Экранируем специальные символы в тексте варианта
        escaped_option = escape_markdown_v2(option_text)
        options_text += f"*{letter}\\)* {escaped_option}\n\n"
    
    # Экранируем специальные символы в тексте вопроса
    escaped_question_text = escape_markdown_v2(question_text)
    
    # Получаем локализованный заголовок вопроса
    questions = get_questions_by_language(language)
    question_header = get_text("question_header", language).format(current=question_number + 1, total=len(questions))
    
    # Форматируем полный текст вопроса с блочным форматированием (вариант 2)
    formatted_text = f"🔷 *{question_header}*\n*{escaped_question_text}*\n\n{options_text}"
    
    return formatted_text, letter_to_number, keyboard_letters, shuffled_options

async def start(update: Update, context: CallbackContext) -> int:
    """
    Отправляет приветственное сообщение и показывает меню выбора языка
    """
    logging.info(f"Получена команда /start от пользователя {update.message.from_user.id}")
    
    # Создаем инлайн-клавиатуру с выбором языка
    keyboard = [
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем сообщение с выбором языка
    await update.message.reply_text(
        "Выберите язык / Choose language:",
        reply_markup=reply_markup
    )

    logging.info(f"Отправлено сообщение с выбором языка пользователю {update.message.from_user.id}")
    
    return CHOOSING_LANGUAGE

async def start_test(update: Update, context: CallbackContext) -> int:
    """
    Начинает тест
    """
    choice = update.message.text
    user_id = update.message.from_user.id
    language = get_user_language(user_id)
    
    if choice == get_text("take_test", language):
        # Очищаем прогресс пользователя перед началом теста
        clear_user_progress(user_id)
        
        # Загружаем первый вопрос
        current_question = 0
        questions = get_questions_by_language(language)
        question = questions[current_question]
        
        # Форматируем вопрос и получаем маппинг ответов
        formatted_text, letter_to_number, keyboard_letters, shuffled_options = format_question_with_options(question, current_question, user_id=user_id)
        
        # Создаем инлайн-клавиатуру с вариантами ответов по 2 в ряд
        keyboard = []
        for i in range(0, len(keyboard_letters), 2):
            row = []
            for j in range(i, min(i+2, len(keyboard_letters))):
                letter = keyboard_letters[j]
                row.append(InlineKeyboardButton(letter, callback_data=f"answer_{letter}"))
            keyboard.append(row)
        
        # Сохраняем начальное состояние с маппингом
        save_user_progress(user_id, {
            "current_question": 0,
            "answers": [],
            "answer_stats": {"1": 0, "2": 0, "3": 0, "4": 0},
            "current_mapping": letter_to_number,
            "shuffled_options": shuffled_options,
            "question_options": {"0": shuffled_options}  # Сохраняем порядок вариантов для первого вопроса
        })
        
        # Отправляем первый вопрос
        await update.message.reply_text(
                formatted_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ANSWERING_QUESTIONS
    else:
        await update.message.reply_text(
            escape_markdown_v2(get_text("thanks_for_interest", language)),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

async def start_new_test(update: Update, context: CallbackContext) -> str:
    """
    Начинает новый тест
    """

    user_id = update.message.from_user.id

async def handle_continue_choice(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает выбор пользователя продолжить тест
    """
    choice = update.message.text
    user_id = update.message.from_user.id
    language = get_user_language(user_id)
    
    if choice == "Продолжить":
        # Загружаем прогресс пользователя
        progress = load_user_progress(user_id)
        current_question = progress.get("current_question", 0)
        questions = get_questions_by_language(language)
        
        if current_question >= len(questions):
            # Если все вопросы закончились, завершаем тест
            return await finish_test(update, context)
        
        # Получаем текущий вопрос
        question = questions[current_question]
        
        # Создаем инлайн-клавиатуру с вариантами ответов
        keyboard = []
        keyboard_letters = ["A", "B", "C", "D"]
        for i in range(0, len(keyboard_letters), 2):
            row = []
            for j in range(i, min(i+2, len(keyboard_letters))):
                letter = keyboard_letters[j]
                row.append(InlineKeyboardButton(letter, callback_data=f"answer_{letter}"))
            keyboard.append(row)
        
        # Отправляем вопрос пользователю
        await update.message.reply_text(
            f"{current_question + 1}. {question['text']}\n\n"
            "Выберите один из вариантов:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ANSWERING_QUESTIONS
    else:
        await update.message.reply_text(
            escape_markdown_v2(get_text("thanks_for_interest", language)),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

async def handle_answer_callback(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает ответы пользователя на вопросы теста через инлайн-кнопки
    """
    query = update.callback_query
    await query.answer()  # Отвечаем на запрос, чтобы убрать часы загрузки
    
    user_id = query.from_user.id
    callback_data = query.data
    language = get_user_language(user_id)
    
    # Проверяем, что это callback для ответа на вопрос или кнопки "Назад"
    if callback_data.startswith("answer_"):
        # Получаем букву ответа
        answer_letter = callback_data.split("_")[1]
        logging.info(f"Получен ответ от пользователя {user_id}: {answer_letter}")
        
        # Получаем текущий прогресс пользователя
        progress = load_user_progress(user_id)
        
        if not progress:
            logging.error(f"Не найден прогресс для пользователя {user_id}")
            await query.message.reply_text(
                "Произошла ошибка при обработке ответа. Пожалуйста, начните тест заново с помощью /start",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
        
        # Получаем номер текущего вопроса
        current_question = progress["current_question"]
        
        # Получаем маппинг букв на номера ответов
        letter_to_number = progress["current_mapping"]
        
        # Получаем номер ответа по букве
        answer_number = letter_to_number.get(answer_letter)
        
        if answer_number is None:
            logging.error(f"Не найден номер ответа для буквы {answer_letter}")
            await query.message.reply_text(
                "Произошла ошибка при обработке ответа. Пожалуйста, начните тест заново с помощью /start",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
        
        # Сохраняем ответ пользователя
        progress["answers"].append(answer_number)
        
        # Обновляем статистику ответов
        progress["answer_stats"][str(answer_number)] += 1
        
        # Логируем обновление статистики
        logging.info(f"Обновлена статистика ответов для пользователя {user_id}: {progress['answer_stats']}")
        
        # Удаляем кнопки и показываем выбранный ответ
        try:
            await query.edit_message_reply_markup(reply_markup=None)
            response_message = await query.message.reply_text(
                get_text("answer_selected", language).format(letter=answer_letter),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            # Сохраняем ID сообщения с выбранным ответом
            progress["last_answer_message_id"] = response_message.message_id
        except Exception as e:
            logging.warning(f"Не удалось удалить кнопки: {e}")
        
        # Получаем вопросы для языка пользователя
        language = get_user_language(user_id)
        questions = get_questions_by_language(language)
        
        # Проверяем, был ли это последний вопрос
        if current_question >= len(questions) - 1:
            # Это был последний вопрос, показываем кнопки "Назад" и "Завершить тест"
            keyboard = [
                [InlineKeyboardButton(get_text("back_to_previous", language), callback_data="back_to_previous")],
                [InlineKeyboardButton(get_text("finish_test", language), callback_data="finish_test")]
            ]
            
            await query.message.reply_text(
                escape_markdown_v2(get_text("last_question_answered", language)),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Сохраняем обновленный прогресс
            save_user_progress(user_id, progress)
            
            return ANSWERING_QUESTIONS
        
        # Переходим к следующему вопросу
        current_question += 1
        progress["current_question"] = current_question
        
        # Загружаем следующий вопрос
        question = questions[current_question]
        
        # Проверяем, есть ли сохраненный порядок вариантов для этого вопроса
        if "question_options" not in progress:
            progress["question_options"] = {}
        
        saved_options = progress["question_options"].get(str(current_question))
        formatted_text, letter_to_number, keyboard_letters, shuffled_options = format_question_with_options(
            question, 
            current_question,
            saved_options,
            user_id=user_id
        )
        
        # Сохраняем порядок вариантов для этого вопроса, если его еще нет
        if str(current_question) not in progress["question_options"]:
            progress["question_options"][str(current_question)] = shuffled_options
        
        # Обновляем маппинг в прогрессе
        progress["current_mapping"] = letter_to_number
        progress["shuffled_options"] = shuffled_options
        
        # Сохраняем обновленный прогресс
        save_user_progress(user_id, progress)
        
        # Создаем инлайн-клавиатуру с вариантами ответов по 2 в ряд
        keyboard = []
        for i in range(0, len(keyboard_letters), 2):
            row = []
            for j in range(i, min(i+2, len(keyboard_letters))):
                letter = keyboard_letters[j]
                row.append(InlineKeyboardButton(letter, callback_data=f"answer_{letter}"))
            keyboard.append(row)
        
        # Добавляем кнопку "Назад" для всех вопросов, кроме первого
        if current_question > 0:
            keyboard.append([InlineKeyboardButton(get_text("back_to_previous", language), callback_data="back_to_previous")])
        
        # Отправляем следующий вопрос
        await query.message.reply_text(
            formatted_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ANSWERING_QUESTIONS
    
    elif callback_data == "back_to_previous":
        # Пользователь хочет вернуться к предыдущему вопросу
        return await go_to_previous_question_inline(update, context)
    
    elif callback_data == "finish_test":
        # Пользователь хочет завершить тест
        return await finish_test_inline(update, context)
    
    return ANSWERING_QUESTIONS

async def go_to_previous_question_inline(update: Update, context: CallbackContext) -> int:
    """
    Возвращает пользователя к предыдущему вопросу
    """
    query = update.callback_query
    user_id = query.from_user.id
    language = get_user_language(user_id)
    
    # Получаем текущий прогресс пользователя
    progress = load_user_progress(user_id)
    
    if not progress:
        logging.error(f"Не найден прогресс для пользователя {user_id}")
        await query.message.reply_text(
            escape_markdown_v2(get_text("no_previous_question", language)),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ANSWERING_QUESTIONS
    
    # Получаем текущий вопрос
    current_question = progress["current_question"]
    
    # Проверяем, что это не первый вопрос
    if current_question <= 0:
        await query.message.reply_text(
            escape_markdown_v2(get_text("no_previous_question", language)),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ANSWERING_QUESTIONS
    
    # Пытаемся удалить сообщение с выбранным ответом
    if "last_answer_message_id" in progress:
        try:
            await context.bot.delete_message(
                chat_id=user_id,
                message_id=progress["last_answer_message_id"]
            )
            logging.info(f"Удалено сообщение с выбранным ответом (ID: {progress['last_answer_message_id']})")
            # Удаляем ID сообщения из прогресса
            del progress["last_answer_message_id"]
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение с выбранным ответом: {e}")
    
    # Удаляем последний ответ из списка ответов
    if progress["answers"]:
        last_answer = progress["answers"].pop()
        # Уменьшаем счетчик для этого типа ответа
        progress["answer_stats"][str(last_answer)] -= 1
    
    # Получаем вопросы для языка пользователя
    language = get_user_language(user_id)
    questions = get_questions_by_language(language)
    
    # Переходим к предыдущему вопросу
    current_question -= 1
    progress["current_question"] = current_question
    
    # Загружаем предыдущий вопрос
    question = questions[current_question]
    
    # Проверяем, есть ли сохраненный порядок вариантов для этого вопроса
    # Для этого нам нужно сохранять порядок вариантов для каждого вопроса
    if "question_options" not in progress:
        progress["question_options"] = {}
    
    saved_options = progress["question_options"].get(str(current_question))
    
    # Форматируем вопрос и получаем маппинг ответов
    formatted_text, letter_to_number, keyboard_letters, shuffled_options = format_question_with_options(
        question, 
        current_question,
        saved_options,
        user_id=user_id
    )
    
    # Сохраняем порядок вариантов для этого вопроса, если его еще нет
    if str(current_question) not in progress["question_options"]:
        progress["question_options"][str(current_question)] = shuffled_options
    
    # Обновляем маппинг в прогрессе
    progress["current_mapping"] = letter_to_number
    progress["shuffled_options"] = shuffled_options
    
    # Сохраняем обновленный прогресс
    save_user_progress(user_id, progress)
    
    # Создаем инлайн-клавиатуру с вариантами ответов по 2 в ряд
    keyboard = []
    for i in range(0, len(keyboard_letters), 2):
        row = []
        for j in range(i, min(i+2, len(keyboard_letters))):
            letter = keyboard_letters[j]
            row.append(InlineKeyboardButton(letter, callback_data=f"answer_{letter}"))
        keyboard.append(row)
    
    # Добавляем кнопку "Назад" для всех вопросов, кроме первого
    if current_question > 0:
        keyboard.append([InlineKeyboardButton(get_text("back_to_previous", language), callback_data="back_to_previous")])
    
    # Отправляем предыдущий вопрос
    await query.message.reply_text(
        formatted_text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(keyboard)
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
    Тестовая функция для отправки сообщения
    """
    user_id = update.message.from_user.id
    language = get_text("language", user_id)
    
    # Создаем инлайн-клавиатуру с вариантами ответов
    keyboard = []
    keyboard_letters = ["A", "B", "C", "D"]
    for i in range(0, len(keyboard_letters), 2):
        row = []
        for j in range(i, min(i+2, len(keyboard_letters))):
            letter = keyboard_letters[j]
            row.append(InlineKeyboardButton(letter, callback_data=f"answer_{letter}"))
        keyboard.append(row)
    
    # Отправляем вопрос пользователю
    await update.message.reply_text(
        f"1. Тестовый вопрос\n\n"
        "Выберите один из вариантов:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
                f"✅ Ответ успешно отправлен пользователю (ID: {user_id})"
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
    if not text:
        return ""
    
    # Проверяем, является ли текст сообщением с результатами теста
    if text.startswith("Спасибо за прохождение тестов") or text.startswith("Thank you for completing the tests"):
        # Для сообщения с результатами теста не применяем экранирование
        return text
    
    # Список специальных символов, которые нужно экранировать
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Экранируем каждый специальный символ
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    
    return text

def format_test_results_message(user_id, language):
    """
    Формирует сообщение с результатами теста на основе статистики ответов пользователя
    """
    # Получаем статистику ответов пользователя
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT answers, answer_stats FROM test_results WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        # Если результаты не найдены, возвращаем стандартное сообщение
        return get_text("results_received", language)
    
    # Получаем базовый шаблон сообщения
    message_template = get_text("results_received", language)
    
    # Получаем статистику ответов
    answer_stats = json.loads(result[1])
    total_answers = sum(answer_stats.values())
    
    # Формируем строки с результатами
    if language == "ru":
        # Для русского языка
        message = message_template.replace("<b>Ранняя фаза</b>", f"<b>Ответов {answer_stats.get('1', 0)} ({(answer_stats.get('1', 0) / total_answers * 100) if total_answers > 0 else 0:.0f}%) Ранняя фаза</b>")
        message = message.replace("<b>Средняя фаза</b>", f"<b>Ответов {answer_stats.get('2', 0)} ({(answer_stats.get('2', 0) / total_answers * 100) if total_answers > 0 else 0:.0f}%) Средняя фаза</b>")
        message = message.replace("<b>Поздняя фаза</b>", f"<b>Ответов {answer_stats.get('3', 0)} ({(answer_stats.get('3', 0) / total_answers * 100) if total_answers > 0 else 0:.0f}%) Поздняя фаза</b>")
        message = message.replace("<b>Переход к жёлтому</b>", f"<b>Ответов {answer_stats.get('4', 0)} ({(answer_stats.get('4', 0) / total_answers * 100) if total_answers > 0 else 0:.0f}%) Переход к жёлтому</b>")
    else:
        # Для английского языка
        message = message_template.replace("<b>Early phase</b>", f"<b>Answers {answer_stats.get('1', 0)} ({(answer_stats.get('1', 0) / total_answers * 100) if total_answers > 0 else 0:.0f}%) Early phase</b>")
        message = message.replace("<b>Middle phase</b>", f"<b>Answers {answer_stats.get('2', 0)} ({(answer_stats.get('2', 0) / total_answers * 100) if total_answers > 0 else 0:.0f}%) Middle phase</b>")
        message = message.replace("<b>Late phase</b>", f"<b>Answers {answer_stats.get('3', 0)} ({(answer_stats.get('3', 0) / total_answers * 100) if total_answers > 0 else 0:.0f}%) Late phase</b>")
        message = message.replace("<b>Transition to Yellow</b>", f"<b>Answers {answer_stats.get('4', 0)} ({(answer_stats.get('4', 0) / total_answers * 100) if total_answers > 0 else 0:.0f}%) Transition to Yellow</b>")
    
    return message

async def finish_test(update: Update, context: CallbackContext) -> int:
    """
    Завершает тест и предлагает пройти второй тест
    """
    try:
        user_id = update.message.from_user.id
        language = get_user_language(user_id)
        
        # Загружаем прогресс пользователя
        progress = load_user_progress(user_id)
        answers = progress.get("answers", [])
        answer_stats = progress.get("answer_stats", {"1": 0, "2": 0, "3": 0, "4": 0})
        
        # Сохраняем статистику ответов для использования после прохождения второго теста
        save_user_progress(user_id, {
            "current_question": len(answers),
            "answers": answers,
            "answer_stats": answer_stats
        })
        
        # Используем локализованную строку для сообщения о втором тесте
        results_message = get_text("first_test_completed", language)
        
        # Отправляем сообщение с результатами пользователю
        await update.message.reply_text(
            results_message,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True
        )
        
        # Обновляем статус теста
        update_test_status(user_id, "completed_first_test")
        
        return WAITING_FOR_SECOND_TEST
    except Exception as e:
        logging.error(f"Ошибка при завершении теста: {str(e)}")
        await update.message.reply_text(
            "Произошла ошибка при обработке результатов теста. Пожалуйста, попробуйте еще раз с помощью /start"
        )
        return ConversationHandler.END

async def handle_second_test_results(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает результаты второго теста (скриншот)
    """
    user_id = update.message.from_user.id
    language = get_user_language(user_id)
    
    logging.info(f"Получен результат второго теста от пользователя {user_id}")
    
    # Проверяем, что пользователь отправил фото или документ
    if update.message.photo or update.message.document:
        # Получаем информацию о пользователе
        username = update.message.from_user.username or ""
        first_name = update.message.from_user.first_name or ""
        
        logging.info(f"Пользователь {user_id} отправил фото или документ")
        
        try:
            # Создаем директорию для скриншотов, если она не существует
            os.makedirs("data/screenshots", exist_ok=True)
            
            # Сохраняем скриншот
            file_path = ""
            if update.message.photo:
                # Получаем фото с наилучшим качеством
                photo = update.message.photo[-1]
                file_id = photo.file_id
                
                # Скачиваем фото
                file = await context.bot.get_file(file_id)
                file_path = f"data/screenshots/{user_id}_{int(time.time())}.jpg"
                await file.download_to_drive(file_path)
                
                logging.info(f"Сохранен скриншот от пользователя {user_id}: {file_path}")
            else:
                # Получаем документ
                document = update.message.document
                file_id = document.file_id
                
                # Проверяем, что это изображение
                mime_type = document.mime_type
                if not mime_type or not mime_type.startswith("image/"):
                    logging.info(f"Пользователь {user_id} отправил документ, который не является изображением")
                    await update.message.reply_text(
                        escape_markdown_v2(get_text("not_image", language)),
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    return WAITING_FOR_SECOND_TEST
                
                # Скачиваем документ
                file = await context.bot.get_file(file_id)
                file_path = f"data/screenshots/{user_id}_{int(time.time())}.jpg"
                await file.download_to_drive(file_path)
                
                logging.info(f"Сохранен скриншот от пользователя {user_id}: {file_path}")
            
            # Обновляем статус теста
            try:
                update_test_status(user_id, "completed")
                logging.info(f"Обновлен статус теста для пользователя {user_id}: completed")
            except Exception as e:
                logging.error(f"Ошибка при обновлении статуса теста: {e}")
            
            # Отправляем сообщение пользователю сразу
            try:
                logging.info(f"Отправляем сообщение пользователю {user_id}")
                message_text = format_test_results_message(user_id, language)
                await update.message.reply_text(
                    message_text,
                    parse_mode=ParseMode.HTML
                )
                logging.info(f"Отправлено сообщение пользователю {user_id}")
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
            
            # Отправляем сообщение администратору
            try:
                # Создаем инлайн-клавиатуру для принятия/отклонения
                keyboard = [
                    [
                        InlineKeyboardButton("Принять", callback_data=f"accept_{user_id}"),
                        InlineKeyboardButton("Отклонить", callback_data=f"reject_{user_id}")
                    ]
                ]
                admin_keyboard = InlineKeyboardMarkup(keyboard)
                
                # Получаем статистику ответов пользователя
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT answers, answer_stats FROM test_results WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                conn.close()
                
                stats_text = ""
                if result:
                    answer_stats = json.loads(result[1])
                    
                    # Проверяем, что все ответы учтены в статистике
                    answers = json.loads(result[0])
                    logging.info(f"Ответы пользователя {user_id}: {answers}")
                    logging.info(f"Статистика ответов до проверки: {answer_stats}")
                    
                    # Убеждаемся, что каждый ответ учтен в статистике
                    for answer in answers:
                        if answer not in answer_stats:
                            answer_stats[answer] = 0
                        
                    # Проверяем, что сумма значений в статистике равна количеству ответов
                    total_answers = sum(answer_stats.values())
                    if total_answers != len(answers):
                        logging.warning(f"Количество ответов в статистике ({total_answers}) не соответствует количеству ответов пользователя ({len(answers)})")
                        
                        # Пересчитываем статистику на основе ответов
                        answer_stats = {"1": 0, "2": 0, "3": 0, "4": 0}
                        for answer in answers:
                            # Убеждаемся, что ответ - это строка, содержащая только цифру
                            if isinstance(answer, str) and answer.isdigit() and answer in answer_stats:
                                answer_stats[answer] += 1
                            elif isinstance(answer, int) or (isinstance(answer, str) and answer.isdigit()):
                                # Преобразуем числовой ответ в строковый ключ
                                answer_key = str(answer)
                                if answer_key in answer_stats:
                                    answer_stats[answer_key] += 1
                                else:
                                    logging.warning(f"Неизвестный тип ответа: {answer}")
                            else:
                                logging.warning(f"Неизвестный формат ответа: {answer}, тип: {type(answer)}")
                        
                        logging.info(f"Статистика ответов после пересчета: {answer_stats}")
                        
                        # Обновляем статистику в базе данных
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE test_results SET answer_stats = ? WHERE user_id = ?",
                            (json.dumps(answer_stats), user_id)
                        )
                        conn.commit()
                        conn.close()
                    
                    total_answers = sum(answer_stats.values())
                    
                    # Формируем статистику в нужном формате
                    for answer_type in sorted(answer_stats.keys()):
                        count = answer_stats[answer_type]
                        percentage = (count / total_answers) * 100 if total_answers > 0 else 0
                        stats_text += f"{answer_type}) {count} ({percentage:.0f}%)\n"
                
                # Создаем сообщение для администратора
                admin_message = f"📊 Новые результаты тестов!\n\nПользователь: {first_name} (@{username})\nID: {user_id}\n\nРезультаты первого теста:\n{stats_text}"
                
                # Отправляем скриншот администратору
                with open(file_path, "rb") as photo_file:
                    await context.bot.send_photo(
                        chat_id=ADMIN_ID,
                        photo=photo_file,
                        caption=admin_message,
                        reply_markup=admin_keyboard
                    )
                
                logging.info(f"Отправлено уведомление администратору о завершении теста пользователем {user_id}")
            except Exception as e:
                logging.error(f"Ошибка при отправке уведомления администратору: {e}")
            
            return ConversationHandler.END
            
        except Exception as e:
            logging.error(f"Ошибка при обработке фотографии: {e}")
            await update.message.reply_text(
                "Произошла ошибка при обработке фотографии. Пожалуйста, попробуйте еще раз.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return WAITING_FOR_SECOND_TEST
    
    return WAITING_FOR_SECOND_TEST

async def handle_photo(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает фотографии, отправленные пользователем
    """
    user_id = update.message.from_user.id
    language = get_user_language(user_id)
    
    logging.info(f"Получена фотография от пользователя {user_id}")
    
    # Получаем информацию о пользователе
    username = update.message.from_user.username or ""
    first_name = update.message.from_user.first_name or ""
    
    # Создаем директорию для скриншотов, если она не существует
    os.makedirs("data/screenshots", exist_ok=True)
    
    # Получаем фото с наилучшим качеством
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    # Скачиваем фото
    try:
        file = await context.bot.get_file(file_id)
        file_path = f"data/screenshots/{user_id}_{int(time.time())}.jpg"
        await file.download_to_drive(file_path)
        
        logging.info(f"Сохранен скриншот от пользователя {user_id}: {file_path}")
        
        # Обновляем статус теста
        update_test_status(user_id, "completed")
        logging.info(f"Обновлен статус теста для пользователя {user_id}: completed")
        
        # Отправляем сообщение пользователю
        message_text = format_test_results_message(user_id, language)
        await update.message.reply_text(
            message_text,
            parse_mode=ParseMode.HTML
        )
        logging.info(f"Отправлено сообщение пользователю {user_id}")
        
        # Отправляем сообщение администратору
        try:
            # Создаем инлайн-клавиатуру для принятия/отклонения
            keyboard = [
                [
                    InlineKeyboardButton("Принять", callback_data=f"accept_{user_id}"),
                    InlineKeyboardButton("Отклонить", callback_data=f"reject_{user_id}")
                ]
            ]
            admin_keyboard = InlineKeyboardMarkup(keyboard)
            
            # Получаем статистику ответов пользователя
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT answers, answer_stats FROM test_results WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            stats_text = ""
            if result:
                answer_stats = json.loads(result[1])
                
                # Проверяем, что все ответы учтены в статистике
                answers = json.loads(result[0])
                logging.info(f"Ответы пользователя {user_id}: {answers}")
                logging.info(f"Статистика ответов до проверки: {answer_stats}")
                
                # Убеждаемся, что каждый ответ учтен в статистике
                for answer in answers:
                    if answer not in answer_stats:
                        answer_stats[answer] = 0
                    
                # Проверяем, что сумма значений в статистике равна количеству ответов
                total_answers = sum(answer_stats.values())
                if total_answers != len(answers):
                    logging.warning(f"Количество ответов в статистике ({total_answers}) не соответствует количеству ответов пользователя ({len(answers)})")
                    
                    # Пересчитываем статистику на основе ответов
                    answer_stats = {"1": 0, "2": 0, "3": 0, "4": 0}
                    for answer in answers:
                        # Убеждаемся, что ответ - это строка, содержащая только цифру
                        if isinstance(answer, str) and answer.isdigit() and answer in answer_stats:
                            answer_stats[answer] += 1
                        elif isinstance(answer, int) or (isinstance(answer, str) and answer.isdigit()):
                            # Преобразуем числовой ответ в строковый ключ
                            answer_key = str(answer)
                            if answer_key in answer_stats:
                                answer_stats[answer_key] += 1
                            else:
                                logging.warning(f"Неизвестный тип ответа: {answer}")
                        else:
                            logging.warning(f"Неизвестный формат ответа: {answer}, тип: {type(answer)}")
                    
                    logging.info(f"Статистика ответов после пересчета: {answer_stats}")
                    
                    # Обновляем статистику в базе данных
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE test_results SET answer_stats = ? WHERE user_id = ?",
                        (json.dumps(answer_stats), user_id)
                    )
                    conn.commit()
                    conn.close()
                
                total_answers = sum(answer_stats.values())
                
                # Формируем статистику в нужном формате
                for answer_type in sorted(answer_stats.keys()):
                    count = answer_stats[answer_type]
                    percentage = (count / total_answers) * 100 if total_answers > 0 else 0
                    stats_text += f"{answer_type}) {count} ({percentage:.0f}%)\n"
            
            # Создаем сообщение для администратора
            admin_message = f"📊 Новые результаты тестов!\n\nПользователь: {first_name} (@{username})\nID: {user_id}\n\nРезультаты первого теста:\n{stats_text}"
            
            # Отправляем скриншот администратору
            with open(file_path, "rb") as photo_file:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=photo_file,
                    caption=admin_message,
                    reply_markup=admin_keyboard
                )
            
            logging.info(f"Отправлено уведомление администратору о завершении теста пользователем {user_id}")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомления администратору: {e}")
        
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Ошибка при обработке фотографии: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обработке фотографии. Пожалуйста, попробуйте еще раз.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAITING_FOR_SECOND_TEST

async def handle_document(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает документы, отправленные пользователем
    """
    user_id = update.message.from_user.id
    language = get_user_language(user_id)
    
    logging.info(f"Получен документ от пользователя {user_id}")
    
    # Получаем информацию о пользователе
    username = update.message.from_user.username or ""
    first_name = update.message.from_user.first_name or ""
    
    # Проверяем, что это изображение
    document = update.message.document
    mime_type = document.mime_type
    
    if not mime_type or not mime_type.startswith("image/"):
        logging.info(f"Пользователь {user_id} отправил документ, который не является изображением")
        await update.message.reply_text(
            escape_markdown_v2(get_text("not_image", language)),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAITING_FOR_SECOND_TEST
    
    # Создаем директорию для скриншотов, если она не существует
    os.makedirs("data/screenshots", exist_ok=True)
    
    # Скачиваем документ
    try:
        file_id = document.file_id
        file = await context.bot.get_file(file_id)
        file_path = f"data/screenshots/{user_id}_{int(time.time())}.jpg"
        await file.download_to_drive(file_path)
        
        logging.info(f"Сохранен скриншот от пользователя {user_id}: {file_path}")
        
        # Обновляем статус теста
        update_test_status(user_id, "completed")
        logging.info(f"Обновлен статус теста для пользователя {user_id}: completed")
        
        # Отправляем сообщение пользователю
        message_text = format_test_results_message(user_id, language)
        await update.message.reply_text(
            message_text,
            parse_mode=ParseMode.HTML
        )
        logging.info(f"Отправлено сообщение пользователю {user_id}")
        
        # Отправляем сообщение администратору
        try:
            # Создаем инлайн-клавиатуру для принятия/отклонения
            keyboard = [
                [
                    InlineKeyboardButton("Принять", callback_data=f"accept_{user_id}"),
                    InlineKeyboardButton("Отклонить", callback_data=f"reject_{user_id}")
                ]
            ]
            admin_keyboard = InlineKeyboardMarkup(keyboard)
            
            # Получаем статистику ответов пользователя
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT answers, answer_stats FROM test_results WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            stats_text = ""
            if result:
                answer_stats = json.loads(result[1])
                
                # Проверяем, что все ответы учтены в статистике
                answers = json.loads(result[0])
                logging.info(f"Ответы пользователя {user_id}: {answers}")
                logging.info(f"Статистика ответов до проверки: {answer_stats}")
                
                # Убеждаемся, что каждый ответ учтен в статистике
                for answer in answers:
                    if answer not in answer_stats:
                        answer_stats[answer] = 0
                    
                # Проверяем, что сумма значений в статистике равна количеству ответов
                total_answers = sum(answer_stats.values())
                if total_answers != len(answers):
                    logging.warning(f"Количество ответов в статистике ({total_answers}) не соответствует количеству ответов пользователя ({len(answers)})")
                    
                    # Пересчитываем статистику на основе ответов
                    answer_stats = {"1": 0, "2": 0, "3": 0, "4": 0}
                    for answer in answers:
                        # Убеждаемся, что ответ - это строка, содержащая только цифру
                        if isinstance(answer, str) and answer.isdigit() and answer in answer_stats:
                            answer_stats[answer] += 1
                        elif isinstance(answer, int) or (isinstance(answer, str) and answer.isdigit()):
                            # Преобразуем числовой ответ в строковый ключ
                            answer_key = str(answer)
                            if answer_key in answer_stats:
                                answer_stats[answer_key] += 1
                            else:
                                logging.warning(f"Неизвестный тип ответа: {answer}")
                        else:
                            logging.warning(f"Неизвестный формат ответа: {answer}, тип: {type(answer)}")
                    
                    logging.info(f"Статистика ответов после пересчета: {answer_stats}")
                    
                    # Обновляем статистику в базе данных
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE test_results SET answer_stats = ? WHERE user_id = ?",
                        (json.dumps(answer_stats), user_id)
                    )
                    conn.commit()
                    conn.close()
                
                total_answers = sum(answer_stats.values())
                
                # Формируем статистику в нужном формате
                for answer_type in sorted(answer_stats.keys()):
                    count = answer_stats[answer_type]
                    percentage = (count / total_answers) * 100 if total_answers > 0 else 0
                    stats_text += f"{answer_type}) {count} ({percentage:.0f}%)\n"
            
            # Создаем сообщение для администратора
            admin_message = f"📊 Новые результаты тестов!\n\nПользователь: {first_name} (@{username})\nID: {user_id}\n\nРезультаты первого теста:\n{stats_text}"
            
            # Отправляем скриншот администратору
            with open(file_path, "rb") as photo_file:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=photo_file,
                    caption=admin_message,
                    reply_markup=admin_keyboard
                )
            
            logging.info(f"Отправлено уведомление администратору о завершении теста пользователем {user_id}")
        except Exception as e:
            logging.error(f"Ошибка при отправке уведомления администратору: {e}")
        
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Ошибка при обработке документа: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обработке документа. Пожалуйста, попробуйте еще раз.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAITING_FOR_SECOND_TEST

def main() -> None:
    """
    Основная функция для запуска бота
    """
    try:
        logging.info("Запуск бота")
        
        # Проверяем, что запущен только один экземпляр бота
        if not check_single_instance():
            logging.error("Бот уже запущен. Завершение работы.")
            return
        
        # Инициализируем базу данных
        init_database()
        
        # Логируем переменные окружения
        logging.info(f"ADMIN_ID: {ADMIN_ID}")
        logging.info(f"ADMIN_IDS: {ADMIN_IDS}")
        logging.info(f"BOT_USERNAME: {BOT_USERNAME}")
        
        # Создаем приложение с увеличенным таймаутом
        application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .connect_timeout(30.0)  # Увеличиваем таймаут соединения до 30 секунд
            .read_timeout(30.0)     # Увеличиваем таймаут чтения до 30 секунд
            .write_timeout(30.0)    # Увеличиваем таймаут записи до 30 секунд
            .get_updates_read_timeout(30.0)  # Устанавливаем таймаут для getUpdates
            .get_updates_write_timeout(30.0) # Устанавливаем таймаут для getUpdates
            .get_updates_connect_timeout(30.0) # Устанавливаем таймаут для getUpdates
            .build()
        )

        # Создаем обработчик диалога
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                CHOOSING_LANGUAGE: [
                    CallbackQueryHandler(handle_language_callback, pattern=r"^lang_")
                ],
                WAITING_FOR_TEST_CHOICE: [
                    CallbackQueryHandler(handle_choice_callback, pattern=r"^start_test$"),
                    CallbackQueryHandler(handle_choice_callback, pattern=r"^choice_no$")
                ],
                ANSWERING_QUESTIONS: [
                    CallbackQueryHandler(handle_answer_callback, pattern=r"^answer_"),
                    CallbackQueryHandler(handle_answer_callback, pattern=r"^back_to_previous$"),
                    CallbackQueryHandler(handle_answer_callback, pattern=r"^finish_test$")
                ],
                WAITING_FOR_SECOND_TEST: [MessageHandler((filters.PHOTO | filters.Document.IMAGE) | filters.TEXT & ~filters.COMMAND, handle_second_test_results)],
                WAITING_FOR_ADMIN_RESPONSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_response)]
            },
            fallbacks=[]  # Убираем обработчик команды cancel
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
        
        # Добавляем обработчик для инлайн-кнопок администратора
        application.add_handler(CallbackQueryHandler(handle_admin_callback, pattern=r"^(accept|reject)_\d+$"))
        
        # Добавляем обработчик для инлайн-кнопок выбора языка
        application.add_handler(CallbackQueryHandler(handle_language_callback, pattern=r"^lang_"))
        
        # Добавляем обработчик для инлайн-кнопок выбора "пройти тест" или "нет, спасибо"
        application.add_handler(CallbackQueryHandler(handle_choice_callback, pattern=r"^choice_"))
        
        # Добавляем обработчик для инлайн-кнопки "start_test"
        application.add_handler(CallbackQueryHandler(handle_choice_callback, pattern=r"^start_test$"))
        
        # Добавляем обработчик для инлайн-кнопок ответов на вопросы теста
        application.add_handler(CallbackQueryHandler(handle_answer_callback, pattern=r"^answer_"))
        
        # Добавляем обработчик для инлайн-кнопок "back_to_previous" и "finish_test"
        application.add_handler(CallbackQueryHandler(handle_answer_callback, pattern=r"^back_to_previous$"))
        application.add_handler(CallbackQueryHandler(handle_answer_callback, pattern=r"^finish_test$"))

        # Добавляем обработчик ошибок с более информативными сообщениями
        async def error_handler(update: object, context: CallbackContext) -> None:
            error_message = str(context.error)
            logging.error(f"Произошла ошибка: {error_message}")
            
            user_message = "Извините, произошла ошибка. "
            
            if "Conflict" in error_message:
                user_message += "Бот уже запущен в другом месте. Пожалуйста, подождите немного и попробуйте снова."
            else:
                user_message += "Пожалуйста, попробуйте еще раз позже или обратитесь к администратору."
            
            if update and isinstance(update, Update) and update.effective_message:
                await update.effective_message.reply_text(user_message)
        
        application.add_error_handler(error_handler)
        
        # Добавляем обработчик для фотографий и документов
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
        
        # Запускаем бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
        logging.info("Бот запущен")
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    lock_file = None
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
    finally:
        logging.info("Завершение работы бота...")
        # Если файл блокировки был создан, закрываем его
        if 'lock_file' in locals() and lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
                os.unlink(LOCK_FILE)
                logging.info(f"Файл блокировки {LOCK_FILE} удален")
            except Exception as e:
                logging.error(f"Ошибка при удалении файла блокировки: {e}")