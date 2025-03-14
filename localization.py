"""
Модуль для работы с локализацией
"""
import importlib
import logging
from typing import Dict, Any, Optional

# Словарь для кэширования загруженных модулей локализации
_locale_cache = {}

def get_text(key: str, language: str = "ru", **kwargs) -> str:
    """
    Получает текст по ключу на нужном языке
    
    Args:
        key: Ключ текста
        language: Код языка (ru, en)
        **kwargs: Параметры для форматирования текста
        
    Returns:
        str: Текст на выбранном языке
    """
    try:
        # Проверяем, загружен ли уже модуль локализации
        if language not in _locale_cache:
            # Загружаем модуль локализации
            _locale_cache[language] = importlib.import_module(f"locales.{language}")
        
        # Получаем текст из модуля
        text = _locale_cache[language].TEXTS.get(key)
        
        if text is None:
            # Если текст не найден на нужном языке, пробуем на русском
            if language != "ru":
                if "ru" not in _locale_cache:
                    _locale_cache["ru"] = importlib.import_module("locales.ru")
                text = _locale_cache["ru"].TEXTS.get(key)
            
            if text is None:
                # Если текст не найден и на русском, возвращаем ключ
                logging.warning(f"Missing text for key: {key}, language: {language}")
                return f"[{key}]"
        
        # Форматируем текст с переданными параметрами
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError as e:
                logging.error(f"Error formatting text for key: {key}, missing parameter: {e}")
                return text
        
        return text
    except Exception as e:
        logging.error(f"Error getting text for key: {key}, language: {language}, error: {e}")
        return f"[{key}]"

def save_user_language(user_id: int, language: str) -> None:
    """
    Сохраняет выбранный пользователем язык
    
    Args:
        user_id: ID пользователя
        language: Код языка (ru, en)
    """
    import sqlite3
    
    conn = sqlite3.connect('data/bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS user_languages (user_id INTEGER PRIMARY KEY, language TEXT)"
    )
    
    cursor.execute(
        "INSERT OR REPLACE INTO user_languages (user_id, language) VALUES (?, ?)",
        (user_id, language)
    )
    
    conn.commit()
    conn.close()

def get_user_language(user_id: int) -> str:
    """
    Получает выбранный пользователем язык
    
    Args:
        user_id: ID пользователя
        
    Returns:
        str: Код языка (ru, en)
    """
    import sqlite3
    
    conn = sqlite3.connect('data/bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS user_languages (user_id INTEGER PRIMARY KEY, language TEXT)"
    )
    
    cursor.execute(
        "SELECT language FROM user_languages WHERE user_id = ?",
        (user_id,)
    )
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] if result else "ru" 