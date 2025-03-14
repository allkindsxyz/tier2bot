"""Модуль с вопросами для теста и функциями для работы с ними."""

import logging
from typing import List, Dict, Any

# Import questions from language-specific modules
from questions_ru import ALL_QUESTIONS as RU_QUESTIONS
from questions_en import ALL_QUESTIONS as EN_QUESTIONS

# Default questions (Russian)
ALL_QUESTIONS = RU_QUESTIONS

def get_questions_by_language(language: str) -> List[Dict[str, Any]]:
    """
    Returns questions based on the selected language
    
    Args:
        language: Language code (ru, en)
        
    Returns:
        List of questions in the selected language
    """
    if language == "ru":
        return RU_QUESTIONS
    elif language == "en":
        return EN_QUESTIONS
    else:
        logging.warning(f"Unknown language: {language}, using Russian questions")
        return RU_QUESTIONS

def validate_question(question):
    """Проверяет корректность формата вопроса."""
    required_keys = {"question", "options"}
    required_options = {"1", "2", "3", "4"}
    
    if not all(key in question for key in required_keys):
        return False
    if not all(option in question["options"] for option in required_options):
        return False
    return True

def validate_all_questions():
    """Проверяет корректность всех вопросов."""
    for i, question in enumerate(ALL_QUESTIONS, 1):
        if not validate_question(question):
            raise ValueError(f"Некорректный формат вопроса {i}")

# Проверяем корректность вопросов при импорте модуля
validate_all_questions()