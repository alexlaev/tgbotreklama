# config/settings.py - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ

from enum import Enum
from typing import Dict, List
import re

class UserState(Enum):
    """Состояния пользователя в диалоге"""
    IDLE = "idle"
    CHOOSING_FIRM_TYPE = "choosing_firm_type"
    ENTERING_FIRM_NAME = "entering_firm_name"
    ENTERING_AD_TEXT = "entering_ad_text"
    ENTERING_JOB_TITLE = "entering_job_title"
    ENTERING_WORKER_COUNT = "entering_worker_count"
    ENTERING_WORK_PERIOD = "entering_work_period"
    ENTERING_WORK_CONDITIONS = "entering_work_conditions"
    ENTERING_REQUIREMENTS = "entering_requirements"
    ENTERING_SALARY = "entering_salary"
    ENTERING_CONTACTS = "entering_contacts"
    REVIEWING_POST = "reviewing_post"
    CHOOSING_PUBLICATION_TYPE = "choosing_publication_type"
    SETTING_SCHEDULE = "setting_schedule"
    ENTERING_PAYMENT_AMOUNT = "entering_payment_amount"
    # Новые состояния для автопостинга и отложенной публикации
    CHOOSING_AUTOPOST_FREQUENCY = "choosing_autopost_frequency"
    CHOOSING_WEEKDAY = "choosing_weekday"
    ENTERING_TIME = "entering_time"
    ENTERING_REPETITIONS = "entering_repetitions"
    CHOOSING_DELAYED_SLOT = "choosing_delayed_slot"
    ENTERING_DELAYED_DATETIME = "entering_delayed_datetime"
    CONFIRMING_DELAYED_PUBLICATION = "confirming_delayed_publication"

class PublicationType(Enum):
    """Типы публикаций"""
    ADVERTISEMENT = "advertisement"
    JOB_SEARCH = "job_search"
    JOB_OFFER = "job_offer"

class FirmType(Enum):
    """Типы фирм"""
    IP = "ИП"
    PHYSICAL = "ФИЗ ЛИЦО"
    LEGAL = "ЮР ЛИЦО"

class AutopostFrequency(Enum):
    """Частота автопостинга"""
    DAILY = "daily"
    WEEKLY = "weekly"

class Weekday(Enum):
    """Дни недели"""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6

# Тексты сообщений
MESSAGES = {
    "welcome_admin": (
        "🔧 Добро пожаловать в административную панель!\n"
        "Выберите действие:"
    ),
    "welcome_user": (
        """Здравствуйте уважаемые коллеги, работодатели и сотрудники.
Данный бот предназначен для размещения в группе 
«Работа Красноярский край» платных публикаций объявлений о работе, поиске работы и сотрудников, а также размещения вашей рекламы. 
Сотни специальностей и вакансий, а так же сотни сотрудников желающих с вами работать в одной команде. 
Размещайте свой пост по поиску сотрудников и предложений открытых вакансий, также предложение соискателей по поиску работы. 
Будем рады размещению ваших постов и рекламных объявлений. """
    ),
    "info_accepted": (
        """🤖 Пользовательское соглашение

Доступные функции данного бота:
📢 Реклама - размещение рекламных объявлений (160₽)
💼 Объявления о работе - поиск сотрудников и вакансий (100₽)
💰 Баланс - проверка текущего баланса
🛒 Магазин - пополнение баланса

Дополнительные возможности:
🔄 Автопостинг - автоматическая публикация с заданной периодичностью
💎 Пакетные скидки - экономия до 20% при покупке нескольких публикаций

Для начала работы используйте /start
С информацией о публикации постов и рекламы в паблике ознакомлен, условия принимаю."""
    ),
    "choose_action": "Выберите действие:",
    "balance_info": "Ваш баланс: {balance} рублей.",
    "insufficient_funds": (
        "У вас недостаточно средств на балансе для такого количества публикаций. "
        "Ваш баланс {balance} рублей. Введите корректное кол-во публикаций "
        "или перейдите в магазин чтобы пополнить баланс"
    ),
    "stop_words_found": (
        "В вашем объявлении были найдены стоп слова, "
        "введите текст объявления заново."
    ),
    "payment_success": (
        "Оплата прошла успешно, вам зачислено {amount} рублей.\n"
        "Ваш баланс: {balance} рублей"
    ),
    "publication_success": "Ваша {type} опубликована {datetime}",
    "schedule_set": (
        "Ваша реклама будет публиковаться раз в {frequency}\n"
        "в {time}"
    ),
    "invalid_time_format": "Некорректное время, введите значение в формате ЧЧ:ММ, например: 23:59",
    "invalid_datetime_format": "Некорректный формат даты и времени введите значение в формате дд.мм.гггг чч:мм, например: 30.05.2025 14:30",
    "autopost_scheduled": "Ваша {type} будет публиковаться раз в {frequency}\nв {time}",
    "delayed_scheduled": "Ваша {type} будет опубликована:\n{schedule_list}"
}

# Клавиатуры
KEYBOARDS = {
    "admin_main": [
        ["Проверить список стоп слов", "Добавить стоп слова"],
        ["Очистить список стоп слов", "Создать публикацию"]
    ],
    "user_main": [
        ["Реклама", "Объявление о работе"],
        ["Баланс", "Магазин"]
    ],
    "firm_types": [
        ["ИП", "ФИЗ ЛИЦО", "ЮР ЛИЦО"],
        ["Назад"]
    ],
    "publication_actions": [
        ["Опубликовать сразу", "Отложенная публикация"],
        ["Автопостинг", "Главная"]
    ],
    "job_types": [
        ["Поиск сотрудника", "Поиск работы"],
        ["Назад"]
    ],
    "autopost_frequency": [
        ["Раз в сутки", "Раз в неделю"],
        ["Назад"]
    ],
    "weekdays": [
        ["Понедельник", "Вторник", "Среда"],
        ["Четверг", "Пятница", "Суббота"],
        ["Воскресенье", "Назад"]
    ]
}

# Конфигурация пакетных скидок
PACKAGE_PRICING = {
    "advertisement": {
        1: 160,
        2: 256,
        3: 384,
        5: 640,
        7: 896,
        10: 1280,
        15: 1920,
        30: 3840
    },
    "job": {
        1: 100,
        2: 160,
        3: 240,
        5: 400,
        7: 560,
        10: 800,
        15: 1200,
        30: 2400
    }
}

# ИСПРАВЛЕНО: Требования к балансу для отложенной публикации согласно ТЗ
DELAYED_BALANCE_REQUIREMENTS = {
    "advertisement": {
        1: 160,  # Автопубликация 1 ≥ 160₽
        2: 256,  # Автопубликация 2 ≥ 256₽
        3: 384   # Автопубликация 3 ≥ 384₽
    },
    "job_offer": {
        1: 160,  # Автопубликация 1 ≥ 160₽
        2: 160,  # Автопубликация 2 ≥ 160₽
        3: 240   # Автопубликация 3 ≥ 240₽
    },
    "job_search": {
        1: 160,  # Автопубликация 1 ≥ 160₽
        2: 160,  # Автопубликация 2 ≥ 160₽
        3: 240   # Автопубликация 3 ≥ 240₽
    },
    "job": {  # Для обратной совместимости
        1: 160,
        2: 160,
        3: 240
    }
}

# Ограничения системы
LIMITS = {
    "max_scheduled_posts": 3,
    "min_balance_for_multiple_posts": {
        "advertisement": 256,
        "job": 160
    },
    "max_repetitions": 30,
    "min_repetitions": 1
}

# ИСПРАВЛЕНО: Форматы для валидации
FORMATS = {
    "time": re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'),
    "datetime": re.compile(r'^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.20[2-9][0-9] ([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
}

# Соответствие дней недели
WEEKDAY_NAMES = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}

# Дополнительные константы
MAX_AD_LENGTH = 4096
MAX_FIRM_NAME_LENGTH = 255
MAX_CONTACT_LENGTH = 500

# Статусы публикаций
PUBLICATION_STATUSES = {
    "draft": "Черновик",
    "scheduled": "Запланирована",
    "published": "Опубликована",
    "failed": "Ошибка публикации"
}

# Типы платежей
PAYMENT_METHODS = {
    "telegram_payments": "Telegram Payments",
    "manual": "Ручное пополнение"
}

# Конфигурация для автопостинга
AUTOPOST_CONFIG = {
    "max_daily_posts": 50,
    "max_weekly_posts": 350,
    "default_timezone": "Europe/Moscow"
}

# Конфигурация для отложенной публикации
DELAYED_POST_CONFIG = {
    "max_delay_days": 365,
    "min_delay_minutes": 5
}

# Сообщения об ошибках
ERROR_MESSAGES = {
    "general_error": "Произошла ошибка. Попробуйте позже или обратитесь в поддержку.",
    "invalid_input": "Некорректный ввод. Попробуйте еще раз.",
    "insufficient_balance": "Недостаточно средств на балансе.",
    "payment_failed": "Ошибка при обработке платежа.",
    "publication_failed": "Ошибка при публикации объявления.",
    "scheduler_error": "Ошибка планировщика.",
    "database_error": "Ошибка базы данных."
}

# Конфигурация безопасности
SECURITY_CONFIG = {
    "max_login_attempts": 5,
    "session_timeout": 3600,  # 1 час
    "max_message_length": 4096,
    "rate_limit_per_minute": 20
}

# Конфигурация уведомлений
NOTIFICATION_CONFIG = {
    "admin_notifications": True,
    "user_notifications": True,
    "payment_notifications": True,
    "publication_notifications": True
}

# Конфигурация логирования
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_rotation": True,
    "max_file_size": "10MB",
    "backup_count": 5
}

# Конфигурация планировщика
SCHEDULER_CONFIG = {
    "timezone": "Europe/Moscow",
    "max_jobs": 1000,
    "job_defaults": {
        "coalesce": False,
        "max_instances": 3
    },
    "executors": {
        "default": {
            "type": "threadpool",
            "max_workers": 20
        }
    }
}

# Валидация данных
VALIDATION_CONFIG = {
    "firm_name": {
        "min_length": 2,
        "max_length": 255,
        "pattern": r'^[a-zA-Zа-яА-Я0-9\s\-_"«».,()]+$'
    },
    "ad_text": {
        "min_length": 10,
        "max_length": 4000
    },
    "contact": {
        "phone_pattern": r'^\+?\d{10,15}$',
        "email_pattern": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    }
}

# Emoji для интерфейса
EMOJI = {
    "advertisement": "📢",
    "job_offer": "💼",
    "job_search": "🔍",
    "balance": "💰",
    "shop": "🛒",
    "back": "◀️",
    "forward": "▶️",
    "home": "🏠",
    "check": "✅",
    "cross": "❌",
    "edit": "✏️",
    "delete": "🗑️",
    "time": "⏰",
    "autopost": "🔄",
    "publish": "📤"
}

# Конфигурация базы данных
DATABASE_CONFIG = {
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": -1,
    "echo": False
}