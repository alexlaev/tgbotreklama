import re
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional

from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class StopWordsFilter:
    """Сервис фильтрации стоп-слов"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def check_text(self, text: str) -> Tuple[bool, List[str]]:
        """
        Проверить текст на наличие стоп-слов
        Args:
            text: Текст для проверки
        Returns:
            Tuple[bool, List[str]]: (содержит_стоп_слова, список_найденных_слов)
        """
        try:
            found_words = self.db.check_text_for_stop_words(text)
            return bool(found_words), found_words
        except Exception as e:
            logger.error(f"Ошибка проверки стоп-слов: {e}")
            return False, []

    def add_stop_words(self, words: List[str], added_by: int) -> bool:
        """
        Добавить стоп-слова в систему
        Args:
            words: Список слов для добавления
            added_by: ID пользователя, добавляющего слова
        Returns:
            bool: Успешность операции
        """
        try:
            # Очищаем и нормализуем слова
            clean_words = []
            for word in words:
                clean_word = self._normalize_word(word)
                if clean_word and len(clean_word) > 1:
                    clean_words.append(clean_word)

            if clean_words:
                self.db.add_stop_words(clean_words, added_by)
                logger.info(f"Добавлено {len(clean_words)} стоп-слов пользователем {added_by}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка добавления стоп-слов: {e}")
            return False

    def get_all_stop_words(self) -> List[str]:
        """Получить все стоп-слова"""
        try:
            return self.db.get_all_stop_words()
        except Exception as e:
            logger.error(f"Ошибка получения стоп-слов: {e}")
            return []

    def clear_all_stop_words(self) -> bool:
        """Очистить все стоп-слова"""
        try:
            self.db.clear_stop_words()
            logger.info("Все стоп-слова очищены")
            return True
        except Exception as e:
            logger.error(f"Ошибка очистки стоп-слов: {e}")
            return False

    def _normalize_word(self, word: str) -> str:
        """
        Нормализовать слово для поиска
        Args:
            word: Исходное слово
        Returns:
            str: Нормализованное слово
        """
        # Убираем пробелы и приводим к нижнему регистру
        normalized = word.strip().lower()
        # Убираем знаки препинания в начале и конце
        normalized = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', normalized)
        return normalized

    def check_word_variants(self, text: str, stop_word: str) -> bool:
        """
        Проверить различные варианты написания слова
        Args:
            text: Текст для поиска
            stop_word: Стоп-слово
        Returns:
            bool: Найдено ли слово или его варианты
        """
        text_lower = text.lower()
        stop_word_lower = stop_word.lower()

        # Прямое вхождение
        if stop_word_lower in text_lower:
            return True

        # Проверка с учетом границ слов
        word_pattern = r'\b' + re.escape(stop_word_lower) + r'\b'
        if re.search(word_pattern, text_lower):
            return True

        # Проверка вариантов с разными окончаниями (для русского языка)
        if len(stop_word_lower) > 3:
            root = stop_word_lower[:-2]  # Убираем последние 2 символа
            root_pattern = r'\b' + re.escape(root) + r'\w*\b'
            if re.search(root_pattern, text_lower):
                return True

        return False

    def get_statistics(self) -> dict:
        """Получить статистику по стоп-словам"""
        try:
            stop_words = self.get_all_stop_words()
            return {
                'total_words': len(stop_words),
                'words': stop_words
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {'total_words': 0, 'words': []}