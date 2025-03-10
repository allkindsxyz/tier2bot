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
import fcntl  # Для блокировки файла

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
WAITING_FOR_INITIAL_CHOICE = 0
WAITING_FOR_BENEFITS_CHOICE = 1
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
    try:
        # Пытаемся создать и заблокировать файл
        lock_file = open(LOCK_FILE, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Записываем PID в файл блокировки
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        
        # Сохраняем файловый дескриптор, чтобы блокировка сохранялась
        # пока программа работает
        return True, lock_file
    except IOError:
        # Не удалось получить блокировку, значит другой экземпляр уже запущен
        logging.error("Другой экземпляр бота уже запущен. Завершение работы.")
        return False, None

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

def format_question_with_options(question: dict, question_number: int, saved_options=None) -> tuple[str, dict, list]:
    """
    Форматирует вопрос с вариантами ответов для отображения
    """
    # Получаем текст вопроса и варианты ответов
    question_text = question.get("question", "").replace("*Вопрос:*\n", "")
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
    
    # Форматируем полный текст вопроса
    formatted_text = f"Вопрос {question_number + 1} из {len(ALL_QUESTIONS)}:\n\n{escaped_question_text}\n\n{options_text}"
    
    return formatted_text, letter_to_number, keyboard_letters, shuffled_options

async def start(update: Update, context: CallbackContext) -> int:
    """
    Отправляет приветственное сообщение и показывает меню
    """
    logging.info(f"Получена команда /start от пользователя {update.message.from_user.id}")
    
    keyboard = [
        ["Да, пожалуйста", "Нет, спасибо"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_message = (
        "*Enter Tier 2* \\- это программа перехода на второй уровень сознания по модели Спиральная Динамика\\.\n\n"
        "Один из авторов модели Клэр Грейвз описывал переход на Tier 2 как фундаментальный сдвиг в сознании\\, "
        "который меняет сам способ мышления\\.\n\n"
        "Если уровни Tier 1 по сути спорят между собой и борются за свою картину мира\\, "
        "на Tier 2 человек впервые начинает видеть систему целиком и понимать ценность всех предыдущих стадий\\.\n\n"
        "Менее 1\\% людей находятся на этом уровне\\. Хотите узнать\\, что дает переход на второй уровень сознания?"
    )
    
    # Путь к изображению
    image_path = "images/tier2_logo.jpg"
    
    try:
        # Проверяем, существует ли файл
        if os.path.exists(image_path):
            # Отправляем одно сообщение с картинкой и текстом
            await update.message.reply_photo(
                photo=open(image_path, 'rb'),
                caption=welcome_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            logging.warning(f"Изображение не найдено: {image_path}")
            # Если изображение не найдено, отправляем только текст
            await update.message.reply_text(
                welcome_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения с изображением: {e}")
        # В случае ошибки отправляем только текст
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return WAITING_FOR_BENEFITS_CHOICE

async def handle_benefits_choice(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает выбор пользователя о просмотре преимуществ
    """
    choice = update.message.text
    logging.info(f"Получен ответ от пользователя: {choice}")
    
    if choice == "Да, пожалуйста" or choice == "📝 Пройти тест":
        if choice == "Да, пожалуйста":
            logging.info("Пользователь выбрал 'Да, пожалуйста'")
            benefits_message = (
                "*Основные преимущества Тиер 2:*\n\n"
                "• *Разрыв с борьбой Тиер 1*\n"
                "Человек перестаёт воспринимать свою текущую систему ценностей как единственно верную и не хочет воевать с другими\\. "
                "Он понимает\\, что каждый уровень имеет своё место и смысл\\.\n\n"
                "• *Гибкость и адаптивность*\n"
                "Вместо привязанности к конкретной идеологии или технике человек начинает свободно использовать инструменты из разных мировоззрений\\, "
                "исходя из ситуации\\.\n\n"
                "• *Системное мышление*\n"
                "Восприятие становится более сложным: человек видит взаимосвязи и динамику развития систем\\, "
                "а не просто «правильные» и «неправильные» вещи\\.\n\n"
                "• *Автономность*\n"
                "Он больше не нуждается в комьюнити или внешнем подтверждении своих взглядов\\, но и не противопоставляет себя обществу\\.\n\n"
                "• *Изменение мотивации*\n"
                "Человек не ищет удовольствий ради удовольствий или просветления ради просветления\\. "
                "Он действует\\, исходя из более глубокого понимания себя и мира\\.\n\n"
                "> _\"Клэр Грейвз описывал переход в Тиер 2 как фундаментальный сдвиг в сознании\\, который меняет сам способ мышления\\\"_\n\n"
            )
            
            keyboard = [
                ["📝 Пройти тест", "Нет, спасибо"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                benefits_message + "\n\n" + "Мы принимаем людей в программу только по результатам двух тестов и оставляем за собой право отказать в участии\\, если посчитаем\\, что вы не готовы\\. Начать первый тест?",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup
            )
            return WAITING_FOR_TEST_CHOICE
        else:
            return await start_test(update, context)
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
        formatted_text, letter_to_number, keyboard_letters, shuffled_options = format_question_with_options(question, current_question)
        
        # Создаем клавиатуру с вариантами ответов по 2 в ряд
        keyboard = [keyboard_letters[i:i+2] for i in range(0, len(keyboard_letters), 2)]
        
        # Сохраняем начальное состояние с маппингом
        save_user_progress(user_id, {
            "current_question": 0,
            "answers": [],
            "answer_stats": {"1": 0, "2": 0, "3": 0, "4": 0},
            "current_mapping": letter_to_number,
            "shuffled_options": shuffled_options
        })
        
        # Отправляем первый вопрос
        await update.message.reply_text(
            formatted_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ANSWERING_QUESTIONS
    else:
        await update.message.reply_text(
            "Спасибо за интерес! Если захотите пройти тест, просто нажмите /start",
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
        keyboard = []
        for letter in keyboard_letters:
            keyboard.append([letter])
        # Убираем кнопку "Отменить"
        # keyboard.append(["Отменить"])
        
        # Отправляем вопрос пользователю
        await update.message.reply_text(
            f"{current_question + 1}. {question['text']}\n\n"
            "Выберите один из вариантов:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
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
    try:
        user_id = update.message.from_user.id
        answer_text = update.message.text
        
        # Загружаем прогресс пользователя
        progress = load_user_progress(user_id)
        current_question = progress.get("current_question", 0)
        answers = progress.get("answers", [])
        answer_stats = progress.get("answer_stats", {"1": 0, "2": 0, "3": 0, "4": 0})
        letter_to_number = progress.get("current_mapping", {})
        shuffled_options = progress.get("shuffled_options", [])
        
        # Проверяем, если пользователь хочет вернуться к предыдущему вопросу
        if answer_text == "Вернуться к предыдущему вопросу":
            return await go_to_previous_question(update, context)
        
        # Проверяем, если пользователь хочет завершить тест
        if answer_text == "Завершить тест":
            return await finish_test(update, context)
        
        # Проверяем, что ответ - одна из букв A, B, C, D
        if answer_text not in letter_to_number:
            await update.message.reply_text(
                "Пожалуйста, выберите один из вариантов ответа (A, B, C, D)."
            )
            return ANSWERING_QUESTIONS
        
        # Получаем номер ответа по букве
        answer_number = letter_to_number[answer_text]
        
        # Сохраняем ответ
        answers.append(answer_number)
        
        # Обновляем статистику ответов
        answer_stats[str(answer_number)] = answer_stats.get(str(answer_number), 0) + 1
        
        # Сохраняем ответ в базу данных
        save_answer_to_db(user_id, current_question, str(answer_number))
        
        # Переходим к следующему вопросу
        current_question += 1
        
        # Проверяем, есть ли еще вопросы
        if current_question >= len(ALL_QUESTIONS):
            # Сохраняем обновленный прогресс
            save_user_progress(user_id, {
                "current_question": current_question,
                "answers": answers,
                "answer_stats": answer_stats,
                "shuffled_options": shuffled_options
            })
            
            # Создаем клавиатуру с кнопками для завершения теста
            keyboard = [
                ["Вернуться к предыдущему вопросу"],
                ["Завершить тест"]
            ]
            
            # Отправляем сообщение о завершении теста с клавиатурой
            await update.message.reply_text(
                "Вы ответили на все вопросы! Вы можете вернуться к предыдущему вопросу или завершить тест.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            
            return ANSWERING_QUESTIONS
        
        # Получаем следующий вопрос
        question = ALL_QUESTIONS[current_question]
        
        # Форматируем следующий вопрос и получаем новый маппинг
        formatted_text, letter_to_number, keyboard_letters, new_shuffled_options = format_question_with_options(question, current_question)
        
        # Создаем клавиатуру с вариантами ответов по 2 в ряд
        keyboard = [keyboard_letters[i:i+2] for i in range(0, len(keyboard_letters), 2)]
        
        # Добавляем кнопку "Вернуться к предыдущему вопросу" только если это не первый вопрос
        if current_question > 0:
            keyboard.append(["Вернуться к предыдущему вопросу"])
        
        # Сохраняем прогресс с новым маппингом
        save_user_progress(user_id, {
            "current_question": current_question,
            "answers": answers,
            "answer_stats": answer_stats,
            "current_mapping": letter_to_number,
            "shuffled_options": new_shuffled_options
        })
        
        # Отправляем следующий вопрос
        await update.message.reply_text(
            formatted_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ANSWERING_QUESTIONS
    except Exception as e:
        logging.error(f"Ошибка при обработке ответа: {str(e)}")
        await update.message.reply_text(
            "Произошла ошибка при обработке вашего ответа. Пожалуйста, попробуйте еще раз с помощью /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def go_to_previous_question(update: Update, context: CallbackContext) -> int:
    """
    Возвращает пользователя к предыдущему вопросу
    """
    try:
        user_id = update.message.from_user.id
        
        # Загружаем прогресс пользователя
        progress = load_user_progress(user_id)
        current_question = progress.get("current_question", 0)
        answers = progress.get("answers", [])
        answer_stats = progress.get("answer_stats", {"1": 0, "2": 0, "3": 0, "4": 0})
        shuffled_options_history = progress.get("shuffled_options_history", {})
        
        # Проверяем, можно ли вернуться к предыдущему вопросу
        if current_question <= 0 or len(answers) == 0:
            await update.message.reply_text(
                "Вы находитесь на первом вопросе, невозможно вернуться назад."
            )
            
            # Повторно отправляем текущий вопрос
            question = ALL_QUESTIONS[current_question]
            formatted_text, letter_to_number, keyboard_letters, shuffled_options = format_question_with_options(question, current_question, progress.get("shuffled_options"))
            
            # Создаем клавиатуру с вариантами ответов по 2 в ряд
            keyboard = [keyboard_letters[i:i+2] for i in range(0, len(keyboard_letters), 2)]
            
            # Сохраняем маппинг
            save_user_progress(user_id, {
                "current_question": current_question,
                "answers": answers,
                "answer_stats": answer_stats,
                "current_mapping": letter_to_number,
                "shuffled_options": shuffled_options
            })
            
            await update.message.reply_text(
                formatted_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return ANSWERING_QUESTIONS
        
        # Удаляем последний ответ из списка ответов
        last_answer = answers.pop()
        
        # Уменьшаем счетчик для этого ответа в статистике
        if last_answer in answer_stats:
            answer_stats[last_answer] = max(0, answer_stats[last_answer] - 1)
        
        # Возвращаемся к предыдущему вопросу
        current_question -= 1
        
        # Получаем предыдущий вопрос
        question = ALL_QUESTIONS[current_question]
        
        # Получаем сохраненный порядок вариантов для этого вопроса
        saved_options = progress.get("shuffled_options")
        
        # Форматируем вопрос и получаем новый маппинг, используя сохраненный порядок
        formatted_text, letter_to_number, keyboard_letters, shuffled_options = format_question_with_options(question, current_question, saved_options)
        
        # Создаем клавиатуру с вариантами ответов по 2 в ряд
        keyboard = [keyboard_letters[i:i+2] for i in range(0, len(keyboard_letters), 2)]
        
        # Добавляем кнопку "Вернуться к предыдущему вопросу" только если это не первый вопрос
        if current_question > 0:
            keyboard.append(["Вернуться к предыдущему вопросу"])
        
        # Сохраняем обновленный прогресс
        save_user_progress(user_id, {
            "current_question": current_question,
            "answers": answers,
            "answer_stats": answer_stats,
            "current_mapping": letter_to_number,
            "shuffled_options": shuffled_options
        })
        
        # Отправляем предыдущий вопрос
        await update.message.reply_text(
            formatted_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ANSWERING_QUESTIONS
    except Exception as e:
        logging.error(f"Ошибка при возврате к предыдущему вопросу: {str(e)}")
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте еще раз с помощью /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

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
    if not text:
        return ""
    
    # Список специальных символов, которые нужно экранировать
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Экранируем каждый специальный символ
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    
    return text

async def finish_test(update: Update, context: CallbackContext) -> int:
    """
    Завершает тест и предлагает пройти второй тест
    """
    try:
        user_id = update.message.from_user.id
        
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
        
        # Формируем сообщение с результатами для пользователя
        results_message = (
            "*Спасибо за прохождение первого теста\\!*\n\n"
            "Для полной оценки вашего уровня, пожалуйста, пройдите второй тест по ссылке:\n"
            "[Пройти второй тест](https://sdtest\\.me/ru)\n\n"
            "После прохождения теста, пожалуйста, *сделайте скриншот результатов* "
            "и отправьте его сюда\\."
        )
        
        # Отправляем сообщение с результатами пользователю
        await update.message.reply_text(
            results_message,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=ReplyKeyboardRemove(),
            disable_web_page_preview=True
        )
        
        # Обновляем статус теста
        update_test_status(user_id, "completed_first_test")
        
        return WAITING_FOR_SECOND_TEST
    except Exception as e:
        logging.error(f"Ошибка при завершении теста: {str(e)}")
        await update.message.reply_text(
            "Произошла ошибка при обработке результатов теста. Пожалуйста, попробуйте еще раз с помощью /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def handle_second_test_results(update: Update, context: CallbackContext) -> int:
    """
    Обрабатывает получение скриншота со вторым тестом
    """
    try:
        # Проверяем, отправил ли пользователь фото или документ
        photo_file = None
        
        if update.message.photo:
            # Получаем файл с наибольшим разрешением
            photo_file = await update.message.photo[-1].get_file()
            logging.info(f"Получено фото от пользователя {update.message.from_user.id}")
        elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('image/'):
            # Получаем документ, если это изображение
            photo_file = await update.message.document.get_file()
            logging.info(f"Получен документ-изображение от пользователя {update.message.from_user.id}")
        
        if not photo_file:
            # Если пользователь отправил текст или другой тип файла
            await update.message.reply_text(
                "Пожалуйста, отправьте скриншот с результатами второго теста в виде изображения.",
                reply_markup=ReplyKeyboardRemove()
            )
            return WAITING_FOR_SECOND_TEST

        user_id = update.message.from_user.id
        
        # Загружаем результаты первого теста и обновляем статистику последнего ответа
        progress = load_user_progress(user_id)
        answers = progress.get("answers", [])
        answer_stats = progress.get("answer_stats", {"1": 0, "2": 0, "3": 0, "4": 0})
        
        # Сохраняем обновленную статистику
        save_user_progress(user_id, {
            "current_question": len(answers),
            "answers": answers,
            "answer_stats": answer_stats
        })

        # Рассчитываем общее количество ответов
        total_answers = sum(int(count) for count in answer_stats.values())
        
        # Формируем статистику с процентами
        stats_text = ""
        for key in sorted(answer_stats.keys()):
            count = int(answer_stats[key])
            percent = (count / total_answers * 100) if total_answers > 0 else 0
            stats_text += f"{key}: {count} ({percent:.1f}%)\n"

        # Отправляем уведомление администратору с результатами обоих тестов
        admin_message = (
            f"📊 Новые результаты тестов!\n\n"
            f"Пользователь: {update.message.from_user.first_name}"
            f" (@{update.message.from_user.username})\n"
            f"ID: {user_id}\n\n"
            f"Результаты первого теста:\n"
            f"{stats_text}\n"
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
                photo=photo_file.file_id,
                caption=admin_message,
                reply_markup=admin_markup
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке скриншота администратору: {str(e)}")
        
        # Отправляем сообщение пользователю
        await update.message.reply_text(
            "Спасибо за прохождение тестов! Мы получили ваши результаты и свяжемся в ближайшее время.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Обновляем статус теста
        update_test_status(user_id, "completed_second_test")
        
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Ошибка при обработке результатов второго теста: {str(e)}")
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте еще раз с помощью /start",
            reply_markup=ReplyKeyboardRemove()
        )
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
        
        # Проверяем, что запущен только один экземпляр бота
        is_single_instance, lock_file = check_single_instance()
        if not is_single_instance:
            logging.error("Бот уже запущен. Завершение работы.")
            return
        
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

        # Добавляем обработчик ошибок с более информативными сообщениями
        async def error_handler(update: object, context: CallbackContext) -> None:
            error_message = str(context.error)
            logging.error(f"Произошла ошибка: {error_message}")
            
            user_message = "Извините, произошла ошибка. "
            if "Timed out" in error_message:
                user_message += "Превышено время ожидания ответа. Пожалуйста, повторите попытку."
            elif "NetworkError" in error_message:
                user_message += "Проблема с сетевым подключением. Пожалуйста, проверьте ваше соединение."
            elif "Conflict: terminated by other getUpdates request" in error_message:
                user_message += "Бот уже запущен в другом месте. Пожалуйста, используйте только один экземпляр бота."
                logging.warning("Обнаружен конфликт с другим экземпляром бота. Завершение работы.")
                return  # Прекращаем обработку ошибки, так как она будет повторяться
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
                lock_file.close()
                if os.path.exists(LOCK_FILE):
                    os.remove(LOCK_FILE)
            except Exception as e:
                logging.error(f"Ошибка при освобождении файла блокировки: {e}")