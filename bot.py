# bot.py - ПОЛНОСТЬЮ ОБНОВЛЕННАЯ ВЕРСИЯ С МЕНЮ КОМАНД

import logging
from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ConversationHandler,
    ContextTypes,
)

from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

# Импорты из вашего проекта
from config.config import load_config
from config.settings import UserState, MESSAGES, KEYBOARDS, PACKAGE_PRICING
from database.db_manager import DatabaseManager
from handlers.admin_handlers import AdminHandlers
from handlers.user_handlers import UserHandlers
from handlers.payment_handlers import PaymentHandlers
from services.payment_service import PaymentService
from services.scheduler import PublicationScheduler
from services.filter_service import StopWordsFilter

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        # Загружаем конфигурацию
        self.bot_config, self.db_config, self.payment_config, self.pricing_config = load_config()

        # Инициализируем базу данных
        self.db_manager = DatabaseManager(
            database_url=self.db_config.database_url,
            echo=self.db_config.echo if hasattr(self.db_config, 'echo') else False
        )
        self.db_manager.create_tables()

        # Инициализируем сервисы
        self.payment_service = PaymentService(self.db_manager)
        self.filter_service = StopWordsFilter(self.db_manager)

        # Инициализируем обработчики
        self.admin_handlers = AdminHandlers(self.db_manager)
        self.user_handlers = UserHandlers(self.db_manager)
        self.payment_handlers = PaymentHandlers(self.db_manager, self.payment_service)

        # Планировщик будет инициализирован после старта event loop
        self.scheduler = None

        # Создаем приложение
        self.application = Application.builder().token(self.bot_config.bot_token).build()

        # Сохраняем конфигурацию в bot_data
        self.application.bot_data['payment_provider_token'] = self.payment_config.provider_token
        self.application.bot_data['group_id'] = self.bot_config.group_id

        # Регистрируем обработчики
        self._register_handlers()

    async def setup_bot_commands(self):
        """Настройка меню команд бота"""
        commands = [
            BotCommand(command="start", description="🚀 Запустить бота"),
            BotCommand(command="help", description="📚 Справка по боту"),
            BotCommand(command="balance", description="💰 Проверить баланс"),
            BotCommand(command="shop", description="🛒 Магазин")
        ]

        try:
            await self.application.bot.set_my_commands(commands)
            logger.info("Меню команд установлено успешно")
        except Exception as e:
            logger.error(f"Ошибка установки меню команд: {e}")

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """🤖 *Справка по боту*

Этот бот предназначен для размещения платных публикаций в группе «Работа Красноярский край».

*Доступные функции:*
📢 *Реклама* - размещение рекламных объявлений (160₽)
💼 *Объявления о работе* - поиск сотрудников и вакансий (100₽)
💰 *Баланс* - проверка вашего текущего баланса
🛒 *Магазин* - пополнение баланса

*Дополнительные возможности:*
🔄 *Автопостинг* - автоматическая публикация с заданной периодичностью
💎 *Пакетные скидки* - экономия до 20% при покупке нескольких публикаций

*Для начала работы используйте /start*
        """

        keyboard = [[InlineKeyboardButton("🚀 Начать работу", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /balance"""
        user_id = update.effective_user.id
        balance = self.db_manager.get_user_balance(user_id)

        text = f"💰 *Ваш баланс:* {int(balance)} рублей"

        keyboard = [
            [InlineKeyboardButton("🛒 Пополнить баланс", callback_data="menu_магазин")],
            [InlineKeyboardButton("📢 Создать рекламу", callback_data="menu_реклама")],
            [InlineKeyboardButton("💼 Создать объявление", callback_data="menu_объявление_о_работе")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    async def _shop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /shop"""
        user_id = update.effective_user.id
        balance = self.db_manager.get_user_balance(user_id)

        text = f"🛒 *Магазин*\n\nВаш баланс: {int(balance)} рублей\n\nВыберите что покупаем:"

        keyboard = [
            [InlineKeyboardButton("📢 Пакеты для рекламы", callback_data="shop_advertisement")],
            [InlineKeyboardButton("💼 Пакеты для объявлений", callback_data="shop_job")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    def _register_handlers(self):
        """Регистрация всех обработчиков"""
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.user_handlers.start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("balance", self._balance_command))
        self.application.add_handler(CommandHandler("shop", self._shop_command))

        # Обработчики callback-кнопок
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.info_publications,
            pattern="^info_publications$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.show_main_menu,
            pattern="^main_menu$"
        ))

        # Меню пользователя
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.show_balance,
            pattern="^menu_баланс$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.show_shop,
            pattern="^menu_магазин$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.start_advertisement,
            pattern="^menu_реклама$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.start_job_posting,
            pattern="^menu_объявление_о_работе$"
        ))

        # Обработчики выбора типа фирмы
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.process_firm_type,
            pattern="^firm_type_"
        ))

        # Обработчики типов объявлений о работе
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.start_job_search_employee,
            pattern="^job_search_employee$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.start_job_search_work,
            pattern="^job_search_work$"
        ))

        # Обработчики кнопок "Назад"
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.back_to_firm_type,
            pattern="^back_to_firm_type$"
        ))

        # Обработчики вариантов публикации
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.show_publication_options,
            pattern="^review_publication$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.publish_immediately,
            pattern="^publish_immediately$"
        ))

        # АВТОПОСТИНГ - обработчики
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.auto_posting,
            pattern="^auto_posting$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.process_frequency_choice,
            pattern="^frequency_(daily|weekly)$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.process_weekday_choice,
            pattern="^weekday_[0-6]$"
        ))

        # Обработчик для кнопки "Редактировать количество"
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.back_to_repetitions_input,
            pattern="^back_to_repetitions$"
        ))

        # Обработчик для возврата к вводу времени
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.back_to_time_input,
            pattern="^back_to_time_input$"
        ))

        # ОТЛОЖЕННАЯ ПУБЛИКАЦИЯ - обработчики
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.delayed_publication,
            pattern="^delayed_publication$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.process_delayed_slot_choice,
            pattern="^delayed_slot_[1-3]$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.remove_delayed_slot,
            pattern="^remove_delayed_slot_[1-3]$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.confirm_delayed_publication,
            pattern="^confirm_delayed_publication$"
        ))

        # ИСПРАВЛЕНИЕ: Обработчик для повторного ввода даты-времени
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.retry_datetime_input,
            pattern="^retry_datetime_input$"
        ))

        # Обработчик для недостаточного баланса
        self.application.add_handler(CallbackQueryHandler(
            self.user_handlers.handle_insufficient_balance,
            pattern="^insufficient_balance$"
        ))

        # Админские обработчики
        self.application.add_handler(CallbackQueryHandler(
            self.admin_handlers.show_stop_words,
            pattern="^admin_проверить_список_стоп_слов$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.admin_handlers.add_stop_words_prompt,
            pattern="^admin_добавить_стоп_слова$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.admin_handlers.clear_stop_words,
            pattern="^admin_очистить_список_стоп_слов$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.admin_handlers.admin_create_publication,
            pattern="^admin_создать_публикацию$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.admin_handlers.admin_back_to_main,
            pattern="^admin_back_to_main$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.admin_handlers.admin_cancel,
            pattern="^admin_cancel$"
        ))

        # Обработчики платежей
        self.application.add_handler(CallbackQueryHandler(
            self.payment_handlers.shop_advertisement_scenario,
            pattern="^shop_advertisement$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.payment_handlers.shop_job_scenario,
            pattern="^shop_job$"
        ))

        self.application.add_handler(CallbackQueryHandler(
            self.payment_handlers.initiate_payment,
            pattern="^pay_"
        ))

        # Обработчики платежных операций
        self.application.add_handler(PreCheckoutQueryHandler(
            self.payment_handlers.precheckout_callback
        ))

        self.application.add_handler(MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            self.payment_handlers.successful_payment_callback
        ))

        # ConversationHandler для стоп-слов
        stop_words_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(
                self.admin_handlers.add_stop_words_prompt,
                pattern="^admin_добавить_стоп_слова$"
            )],
            states={
                "WAITING_STOP_WORDS": [MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self.admin_handlers.process_stop_words
                )]
            },
            fallbacks=[CallbackQueryHandler(
                self.admin_handlers.admin_cancel,
                pattern="^admin_cancel$"
            )],
            per_message=False
        )

        self.application.add_handler(stop_words_conv)

        # Обработчик текстовых сообщений в зависимости от состояния
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_text_message
        ))

        # Обработчик контактов
        self.application.add_handler(MessageHandler(
            filters.CONTACT,
            self._handle_contact
        ))

        # Обработчик ошибок
        self.application.add_error_handler(self._error_handler)

    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений в зависимости от состояния пользователя"""
        user_id = update.effective_user.id
        state = self.db_manager.get_user_state(user_id)

        logger.info(f"Обработка текстового сообщения от пользователя {user_id}, состояние: {state}")

        try:
            if state == "waiting_stop_words":
                await self.admin_handlers.process_stop_words(update, context)
            elif state in ["entering_payment_amount_ad", "entering_payment_amount_job"]:
                await self.payment_handlers.process_payment_amount(update, context)
            elif state == UserState.ENTERING_FIRM_NAME.value:
                await self.user_handlers.process_firm_name(update, context)
            elif state == UserState.ENTERING_AD_TEXT.value:
                await self.user_handlers.process_ad_text(update, context)
            elif state == UserState.ENTERING_JOB_TITLE.value:
                await self.user_handlers.process_job_title(update, context)
            elif state == UserState.ENTERING_WORKER_COUNT.value:
                await self.user_handlers.process_worker_count(update, context)
            elif state == UserState.ENTERING_WORK_PERIOD.value:
                await self.user_handlers.process_work_period(update, context)
            elif state == UserState.ENTERING_WORK_CONDITIONS.value:
                await self.user_handlers.process_work_conditions(update, context)
            elif state == UserState.ENTERING_REQUIREMENTS.value:
                await self.user_handlers.process_requirements(update, context)
            elif state == UserState.ENTERING_SALARY.value:
                await self.user_handlers.process_salary(update, context)
            elif state == UserState.ENTERING_CONTACTS.value:
                await self.user_handlers.process_contacts(update, context)
            elif state == UserState.ENTERING_TIME.value:
                await self.user_handlers.process_time_input(update, context)
            elif state == UserState.ENTERING_REPETITIONS.value:
                await self.user_handlers.process_repetitions_input(update, context)
            elif state == UserState.ENTERING_DELAYED_DATETIME.value:
                await self.user_handlers.process_delayed_datetime_input(update, context)
            else:
                # Обработка по умолчанию
                await update.message.reply_text("Используйте команду /start для начала работы с ботом.")

        except Exception as e:
            logger.error(f"Ошибка обработки текстового сообщения: {e}")
            await update.message.reply_text("Произошла ошибка. Попробуйте позже или обратитесь в поддержку.")

    async def _handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка отправленного контакта"""
        try:
            contact = update.message.contact
            user_id = update.effective_user.id

            # Сохраняем контакт в сессии
            session_data = self.db_manager.get_session_data(user_id)
            session_data['contacts'] = f"+{contact.phone_number}"
            self.db_manager.save_session_data(user_id, session_data)

            await self.user_handlers.review_publication(update, context)

        except Exception as e:
            logger.error(f"Ошибка обработки контакта: {e}")
            await update.message.reply_text("Произошла ошибка. Попробуйте позже или обратитесь в поддержку.")

    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка при обновлении {update}: {context.error}")

        try:
            if update and update.effective_message:
                keyboard = [[InlineKeyboardButton("🏠 Главная", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.effective_message.reply_text(
                    "Произошла ошибка. Попробуйте позже или обратитесь в поддержку.",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Ошибка в error_handler: {e}")

    async def on_startup(self):
        """Инициализация планировщика после старта event loop"""
        try:
            # Устанавливаем меню команд
            await self.setup_bot_commands()

            self.scheduler = PublicationScheduler(
                self.db_manager,
                self.application.bot,
                self.bot_config.group_id
            )
            self.user_handlers.set_scheduler(self.scheduler)
            logger.info("✅ Планировщик инициализирован")
            logger.info("✅ Меню команд настроено")
        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}")

    async def on_shutdown(self):
        """Остановка планировщика при завершении работы"""
        try:
            if self.scheduler:
                self.scheduler.shutdown()
            logger.info("Планировщик остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки планировщика: {e}")

    def run_bot(self):
        """Запуск бота"""
        import asyncio

        async def main():
            try:
                # Инициализация планировщика после запуска event loop
                await self.on_startup()

                # Запуск бота
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling()
                logger.info("🤖 Бот запущен и готов к работе!")
                logger.info("📋 Меню команд доступно пользователям")

                # Ожидание завершения работы
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Получен сигнал остановки")

            except Exception as e:
                logger.error(f"Критическая ошибка запуска бота: {e}")
            finally:
                # Корректное завершение работы
                await self.on_shutdown()
                if self.application.updater.running:
                    await self.application.updater.stop()
                if self.application.running:
                    await self.application.stop()
                await self.application.shutdown()
                logger.info("Бот остановлен")

        # Запуск с обработкой исключений
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Получен сигнал завершения работы")
        except Exception as e:
            logger.error(f"Фатальная ошибка: {e}")


if __name__ == "__main__":
    try:
        bot = TelegramBot()
        bot.run_bot()
    except Exception as e:
        logger.error(f"Ошибка создания бота: {e}")
        print(f"Ошибка запуска бота: {e}")