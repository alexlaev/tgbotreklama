# config/config.py - Исправленная версия
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Конфигурация основных параметров бота"""
    bot_token: str
    group_id: int
    webhook_url: Optional[str] = None
    webhook_port: int = 8443
    debug_mode: bool = False


@dataclass
class DatabaseConfig:
    """Конфигурация базы данных"""
    database_url: str = "sqlite:///bot_database.db"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


@dataclass
class PaymentConfig:
    """Конфигурация платежной системы"""
    provider_token: str
    test_mode: bool = True
    currency: str = "RUB"


@dataclass
class PricingConfig:
    """Конфигурация ценообразования"""
    ad_price: int = 160  # Цена за рекламу
    job_price: int = 100  # Цена за объявление о работе
    bulk_discount: float = 0.20  # Скидка 20% для пакетов


def load_config() -> tuple[BotConfig, DatabaseConfig, PaymentConfig, PricingConfig]:
    """Загрузка конфигурации из переменных окружения"""

    # Получаем переменные окружения с проверкой
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        # Для разработки используем тестовый токен
        print("⚠️  ВНИМАНИЕ: Используется тестовый токен! Установите BOT_TOKEN в переменные окружения для продакшена")
        bot_token = "7642934797:AAH6uAq2HlIejo7xX8Tk_yBp-kYUcQrJytk"

    group_id_str = os.getenv("GROUP_ID")
    if not group_id_str:
        print("⚠️  ВНИМАНИЕ: Используется тестовый GROUP_ID! Установите GROUP_ID в переменные окружения")
        group_id = -1002850839936
    else:
        try:
            group_id = int(group_id_str)
        except ValueError:
            raise ValueError("GROUP_ID должен быть числом")

    payment_token = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
    if not payment_token:
        print("⚠️  ВНИМАНИЕ: PAYMENT_PROVIDER_TOKEN не установлен. Платежи работать не будут!")

    bot_config = BotConfig(
        bot_token=bot_token,
        group_id=group_id,
        webhook_url=os.getenv("WEBHOOK_URL"),
        debug_mode=os.getenv("DEBUG", "False").lower() == "true"
    )

    db_config = DatabaseConfig(
        database_url=os.getenv("DATABASE_URL", "sqlite:///bot_database.db"),
        echo=bot_config.debug_mode
    )

    payment_config = PaymentConfig(
        provider_token=payment_token,
        test_mode=os.getenv("PAYMENT_TEST_MODE", "True").lower() == "true"
    )

    pricing_config = PricingConfig()

    return bot_config, db_config, payment_config, pricing_config