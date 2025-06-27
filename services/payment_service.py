from typing import Optional, Dict, Any
import logging
from decimal import Decimal

from database.db_manager import DatabaseManager
from config.settings import PACKAGE_PRICING

logger = logging.getLogger(__name__)


class PaymentService:
    """Сервис для обработки платежей"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def calculate_cost(self, service_type: str, quantity: int) -> float:
        """Рассчитать стоимость услуги с учетом скидок"""
        if service_type not in PACKAGE_PRICING:
            raise ValueError(f"Неизвестный тип услуги: {service_type}")

        pricing = PACKAGE_PRICING[service_type]

        # Если есть точное соответствие количества, используем его
        if quantity in pricing:
            return pricing[quantity]

        # Иначе рассчитываем с учетом скидки для количества >= 2
        base_price = pricing[1]
        if quantity >= 2:
            # Применяем скидку 20%
            total_cost = base_price * quantity * 0.8
            return total_cost

        return base_price * quantity

    def check_balance(self, user_id: int, required_amount: float) -> bool:
        """Проверить достаточность средств на балансе"""
        return self.db.check_balance(user_id, required_amount)

    def process_payment(self, user_id: int, amount: float, description: str = None) -> bool:
        """Обработать платеж (списание с баланса)"""
        try:
            if self.check_balance(user_id, amount):
                success = self.db.update_balance(user_id, -amount)
                if success:
                    logger.info(f"Списано {amount} рублей с баланса пользователя {user_id}")
                    return True
                else:
                    logger.error(f"Ошибка списания {amount} рублей с баланса пользователя {user_id}")
                    return False
            else:
                logger.warning(f"Недостаточно средств у пользователя {user_id} для списания {amount}")
                return False
        except Exception as e:
            logger.error(f"Ошибка обработки платежа для пользователя {user_id}: {e}")
            return False

    def add_funds(self, user_id: int, amount: float) -> bool:
        """Пополнить баланс пользователя"""
        try:
            success = self.db.update_balance(user_id, amount)
            if success:
                logger.info(f"Пополнен баланс пользователя {user_id} на {amount} рублей")
                return True
            else:
                logger.error(f"Ошибка пополнения баланса пользователя {user_id}")
                return False
        except Exception as e:
            logger.error(f"Ошибка пополнения баланса для пользователя {user_id}: {e}")
            return False

    def get_balance(self, user_id: int) -> float:
        """Получить текущий баланс пользователя"""
        return self.db.get_user_balance(user_id)

    def validate_payment_amount(self, amount: float) -> bool:
        """Валидация суммы платежа"""
        if amount <= 0:
            return False
        if amount > 100000:  # Максимальная сумма платежа
            return False
        return True

    def get_pricing_info(self, service_type: str) -> Dict[int, float]:
        """Получить информацию о ценах для типа услуги"""
        return PACKAGE_PRICING.get(service_type, {})

    def calculate_optimal_package(self, service_type: str, desired_quantity: int) -> Dict[str, Any]:
        """Рассчитать оптимальный пакет для желаемого количества"""
        pricing = self.get_pricing_info(service_type)

        if not pricing:
            return {}

        # Находим ближайший пакет
        available_packages = sorted(pricing.keys())
        optimal_package = None

        for package_size in available_packages:
            if package_size >= desired_quantity:
                optimal_package = package_size
                break

        if optimal_package is None:
            # Если нет подходящего пакета, рассчитываем индивидуально
            optimal_package = desired_quantity

        cost = self.calculate_cost(service_type, optimal_package)

        return {
            "package_size": optimal_package,
            "cost": cost,
            "savings": (pricing[1] * optimal_package - cost) if optimal_package > 1 else 0
        }
