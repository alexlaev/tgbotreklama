# Исправленный файл handlers/payment_handlers.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, PreCheckoutQuery
from telegram.ext import ContextTypes
import logging

from database.db_manager import DatabaseManager
from config.settings import PACKAGE_PRICING, MESSAGES
from services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class PaymentHandlers:
    """Обработчики платежей"""

    def __init__(self, db_manager: DatabaseManager, payment_service: PaymentService):
        self.db = db_manager
        self.payment_service = payment_service

    async def shop_advertisement_scenario(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сценарий покупки рекламы"""
        query = update.callback_query
        await query.answer()

        pricing_text = self._format_pricing_text("advertisement")
        text = f"Введите сумму на которую хотите пополнить баланс.\n\n{pricing_text}"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

        user_id = update.effective_user.id
        self.db.update_user_state(user_id, "entering_payment_amount_ad")

    async def shop_job_scenario(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сценарий покупки объявления о работе"""
        query = update.callback_query
        await query.answer()

        pricing_text = self._format_pricing_text("job")
        text = f"Введите сумму на которую хотите пополнить баланс.\n\n{pricing_text}"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

        user_id = update.effective_user.id
        self.db.update_user_state(user_id, "entering_payment_amount_job")

    def _format_pricing_text(self, service_type: str) -> str:
        """Форматирование текста с ценами"""
        if service_type == "advertisement":
            base_text = "Публикация Рекламы на платной основе.\n1 размещение в группе - 160 ₽\n\n"
            pricing = PACKAGE_PRICING["advertisement"]
            base_price = 160
        else:
            base_text = "Публикация объявлений на платной основе.\n1 размещение в группе - 100 ₽\n\n"
            pricing = PACKAGE_PRICING["job"]
            base_price = 100

        discount_text = "Также есть возможность пакетного размещения с 20% скидкой:\n"
        for count, price in pricing.items():
            if count > 1:
                original_price = count * base_price
                discount_text += f"{count} размещения - {price} ₽ (вместо {original_price} ₽)\n"

        return base_text + discount_text

    async def process_payment_amount(self, service_type: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка введенной суммы платежа"""
        user_id = update.effective_user.id
        text = update.message.text

        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
        except ValueError:
            await update.message.reply_text(
                "❌ Некорректный формат суммы. Введите числовое значение."
            )
            return

        # Сохраняем сумму в сессии
        session_data = self.db.get_session_data(user_id)
        session_data['payment_amount'] = amount
        self.db.save_session_data(user_id, session_data)

        # Показываем кнопки для оплаты
        if service_type == "advertisement":
            keyboard = [
                [InlineKeyboardButton("💳 Перейти к оплате", callback_data=f"pay_{amount}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="shop_advertisement")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            keyboard = [
                [InlineKeyboardButton("💳 Перейти к оплате", callback_data=f"pay_{amount}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="shop_job")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

        
        await update.message.reply_text(
            f"Оплата {int(amount)} рублей",
            reply_markup=reply_markup
        )

        self.db.update_user_state(user_id, "confirming_payment")

    async def initiate_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Инициация платежа"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        amount_str = query.data.split("_")[1]
        amount = float(amount_str)

        # Создаем платеж в базе данных
        payment_id = self.db.create_payment(user_id, amount, "telegram_payments")

        # Сохраняем ID платежа в контексте
        context.user_data['payment_id'] = payment_id

        # Создаем инвойс для Telegram Payments
        title = "Пополнение баланса"
        description = f"Пополнение баланса на {int(amount)} рублей"
        payload = f"payment_{payment_id}"
        currency = "RUB"
        prices = [LabeledPrice("Пополнение баланса", int(amount * 100))]  # В копейках

        try:
            await context.bot.send_invoice(
                chat_id=user_id,
                title=title,
                description=description,
                payload=payload,
                provider_token=context.bot_data.get('payment_provider_token', ''),
                currency=currency,
                prices=prices,
                start_parameter="payment",
                is_flexible=False
            )
        except Exception as e:
            logger.error(f"Ошибка создания инвойса: {e}")
            await query.edit_message_text(
                "❌ Ошибка при создании платежа. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главная", callback_data="main_menu")
                ]])
            )

    async def precheckout_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Предварительная проверка платежа"""
        query: PreCheckoutQuery = update.pre_checkout_query

        # Проверяем валидность платежа
        if query.invoice_payload.startswith("payment_"):
            await query.answer(ok=True)
        else:
            await query.answer(
                ok=False,
                error_message="Что-то пошло не так с платежом. Попробуйте еще раз."
            )

    async def successful_payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка успешного платежа"""
        payment = update.message.successful_payment
        user_id = update.effective_user.id

        # Извлекаем ID платежа из payload
        payment_id = int(payment.invoice_payload.split("_")[1])

        # Завершаем платеж в базе данных
        success = self.db.complete_payment(payment_id, payment.telegram_payment_charge_id)

        if success:
            amount = payment.total_amount / 100  # Конвертируем из копеек
            balance = self.db.get_user_balance(user_id)

            response_text = MESSAGES["payment_success"].format(
                amount=int(amount),
                balance=int(balance)
            )

            keyboard = [[InlineKeyboardButton("Создать публикацию", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(response_text, reply_markup=reply_markup)

            # Очищаем состояние пользователя
            self.db.update_user_state(user_id, "idle")
            self.db.clear_session_data(user_id)
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке платежа. Обратитесь в поддержку."
            )

    async def failed_payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка неуспешного платежа"""
        user_id = update.effective_user.id

        text = "Ваш платеж не найден, попробуйте позже"
        keyboard = [[InlineKeyboardButton("🏠 Главная", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)

        # Очищаем состояние пользователя
        self.db.update_user_state(user_id, "idle")
