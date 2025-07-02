from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, \
    ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
import re
import os
import logging

from database.db_manager import DatabaseManager
from config.settings import (
    MESSAGES, KEYBOARDS, UserState, FirmType, PACKAGE_PRICING,
    DELAYED_BALANCE_REQUIREMENTS, FORMATS, WEEKDAY_NAMES, ERROR_MESSAGES
)
from services.filter_service import StopWordsFilter
from services.scheduler import PublicationScheduler

logger = logging.getLogger(__name__)


class UserHandlers:
    """Обработчики для обычных пользователей"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.filter_service = StopWordsFilter(db_manager)
        self.scheduler = None

    def set_scheduler(self, scheduler: PublicationScheduler):
        """Установить планировщик"""
        self.scheduler = scheduler

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user

        # Создаем или получаем пользователя
        db_user = self.db.get_or_create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        # Проверяем права администратора
        if self.db.is_user_admin(user.id):
            from .admin_handlers import AdminHandlers
            admin_handlers = AdminHandlers(self.db)
            await admin_handlers.admin_start(update, context)
        else:
            # Показываем приветственное сообщение для обычного пользователя
            keyboard = [[InlineKeyboardButton(
                "Создать публикацию",
                callback_data="main_menu"
            )]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                MESSAGES["welcome_user"],
                reply_markup=reply_markup
            )

    async def info_publications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка информации о публикациях"""
        query = update.callback_query
        await query.answer()

        keyboard = [[InlineKeyboardButton("Создать публикацию", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            MESSAGES["info_accepted"],
            reply_markup=reply_markup
        )

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать главное меню"""
        if update.callback_query:
            query = update.callback_query
            await query.answer()

            keyboard = [
                [InlineKeyboardButton("📢 Размещение рекламы", callback_data="menu_реклама")],
                [InlineKeyboardButton("💼 Размещение объявлений о работе", callback_data="menu_объявление_о_работе")],
                [InlineKeyboardButton("💰 Баланс", callback_data="menu_баланс"),
                 InlineKeyboardButton("🛒 Магазин", callback_data="menu_магазин")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                MESSAGES["choose_action"],
                reply_markup=reply_markup
            )
        else:
            keyboard = [
                [InlineKeyboardButton("📢 Размещение рекламы", callback_data="menu_реклама")],
                [InlineKeyboardButton("💼 Размещение объявлений о работе", callback_data="menu_объявление_о_работе")],
                [InlineKeyboardButton("💰 Баланс", callback_data="menu_баланс"),
                 InlineKeyboardButton("🛒 Магазин", callback_data="menu_магазин")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                MESSAGES["choose_action"],
                reply_markup=reply_markup
            )

    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать баланс пользователя"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        balance = self.db.get_user_balance(user_id)

        text = MESSAGES["balance_info"].format(balance=int(balance))

        keyboard = [
            [InlineKeyboardButton("🛒 Магазин", callback_data="menu_магазин")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def show_shop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать магазин"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        balance = self.db.get_user_balance(user_id)

        text = f"Ваш баланс: {int(balance)} рублей\nВыберите что покупаем:"

        keyboard = [
            [InlineKeyboardButton("📢 Размещение рекламы", callback_data="shop_advertisement")],
            [InlineKeyboardButton("💼 Размещение объявлений о работе", callback_data="shop_job")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def start_advertisement(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать создание рекламы"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        # Проверяем права админа или баланс
        if not self.db.is_user_admin(user_id):
            balance = self.db.get_user_balance(user_id)
            if balance < 160:
                # Перенаправляем в магазин
                from .payment_handlers import PaymentHandlers
                payment_handlers = PaymentHandlers(self.db, None)
                await payment_handlers.shop_advertisement_scenario(update, context)
                return

        # Показываем выбор типа фирмы
        await self.choose_firm_type(update, context, "advertisement")

    async def start_job_posting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать создание объявления о работе"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        # Проверяем права админа или баланс
        if not self.db.is_user_admin(user_id):
            balance = self.db.get_user_balance(user_id)
            if balance < 100:
                # Перенаправляем в магазин
                from .payment_handlers import PaymentHandlers
                payment_handlers = PaymentHandlers(self.db, None)
                await payment_handlers.shop_job_scenario(update, context)
                return

        # Показываем выбор типа объявления
        keyboard = [
            [InlineKeyboardButton("👥 Поиск сотрудника", callback_data="job_search_employee")],
            [InlineKeyboardButton("💼 Поиск работы", callback_data="job_search_work")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Выберите тип объявления:",
            reply_markup=reply_markup
        )

    async def start_job_search_employee(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать создание объявления поиск сотрудника"""
        await self.choose_firm_type(update, context, "job_offer")

    async def start_job_search_work(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать создание объявления поиск работы"""
        await self.choose_firm_type(update, context, "job_search")

    async def choose_firm_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE, pub_type: str):
        """Выбор типа фирмы"""
        if update.callback_query:
            query = update.callback_query
            await query.answer()

            user_id = update.effective_user.id

            # Сохраняем тип публикации в сессии
            session_data = self.db.get_session_data(user_id)
            session_data['publication_type'] = pub_type
            self.db.save_session_data(user_id, session_data)

            keyboard = [
                [InlineKeyboardButton("ИП", callback_data="firm_type_ИП")],
                [InlineKeyboardButton("ФИЗ ЛИЦО", callback_data="firm_type_ФИЗ ЛИЦО")],
                [InlineKeyboardButton("ЮР ЛИЦО", callback_data="firm_type_ЮР ЛИЦО")],
                [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            text = "От какого лица будет идти размещение:"
            await query.edit_message_text(text, reply_markup=reply_markup)
            self.db.update_user_state(update.effective_user.id, UserState.CHOOSING_FIRM_TYPE.value)

    async def process_firm_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора типа фирмы"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        firm_type = query.data.split("_")[-1]

        logger.info(f"Пользователь {user_id} выбрал тип фирмы: {firm_type}")

        # Сохраняем тип фирмы в сессии
        session_data = self.db.get_session_data(user_id)
        session_data['firm_type'] = firm_type
        self.db.save_session_data(user_id, session_data)

        # Переходим к вводу названия фирмы
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_firm_type")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Введите название фирмы:",
            reply_markup=reply_markup
        )
        self.db.update_user_state(user_id, UserState.ENTERING_FIRM_NAME.value)

    async def back_to_firm_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к выбору типа фирмы"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)
        pub_type = session_data.get('publication_type', 'advertisement')

        await self.choose_firm_type(update, context, pub_type)

    async def process_firm_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка названия фирмы"""
        user_id = update.effective_user.id
        firm_name = update.message.text

        logger.info(f"Обработка названия фирмы '{firm_name}' для пользователя {user_id}")

        # Сохраняем название фирмы
        session_data = self.db.get_session_data(user_id)
        session_data['firm_name'] = firm_name
        self.db.save_session_data(user_id, session_data)

        # Определяем следующий шаг в зависимости от типа публикации
        pub_type = session_data.get('publication_type', 'advertisement')

        if pub_type == 'advertisement':
            next_text = "Введите текст для объявления:"
            next_state = UserState.ENTERING_AD_TEXT.value
        elif pub_type == 'job_offer':
            next_text = """Введите название вакансии/специальности на которую ищите специалиста:
Можете воспользоваться сервисом для просмотра наименований профессий https://окпдтр.рф/"""
            next_state = UserState.ENTERING_JOB_TITLE.value
        else:  # job_search
            next_text = """Введите название вакансии/специальности на которую хотите устроиться:
Можете воспользоваться сервисом для просмотра наименований профессий https://окпдтр.рф/"""
            next_state = UserState.ENTERING_JOB_TITLE.value

        keyboard = [[InlineKeyboardButton("◀️ Начать заново", callback_data="back_to_firm_type")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(next_text, reply_markup=reply_markup)
        self.db.update_user_state(user_id, next_state)

    async def process_ad_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текста рекламы"""
        user_id = update.effective_user.id
        ad_text = update.message.text

        # Сохраняем текст рекламы
        session_data = self.db.get_session_data(user_id)
        session_data['ad_text'] = ad_text
        self.db.save_session_data(user_id, session_data)

        # Переходим к вводу контактов
        keyboard = [
            [KeyboardButton("📞 Поделиться вашим номером телефона", request_contact=True)],
            [InlineKeyboardButton("◀️ Начать заново", callback_data="back_to_firm_type")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard[1:])  # Только инлайн кнопки для reply_markup

        await update.message.reply_text(
            "Укажите ваш(и) контакт(ы), либо нажмите на кнопку для автоматической отправки:",
            reply_markup=reply_markup
        )

        # Также отправляем клавиатуру с кнопкой контакта
        contact_markup = ReplyKeyboardMarkup([[keyboard[0][0]]], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Или нажмите кнопку ниже:",
            reply_markup=contact_markup
        )

        self.db.update_user_state(user_id, UserState.ENTERING_CONTACTS.value)

    async def process_job_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка названия вакансии"""
        user_id = update.effective_user.id
        job_title = update.message.text

        # Сохраняем название вакансии
        session_data = self.db.get_session_data(user_id)
        session_data['job_title'] = job_title
        pub_type = session_data.get('publication_type')
        self.db.save_session_data(user_id, session_data)

        if pub_type == 'job_offer':
            next_text = "Укажите требуемое количество работников по выбранной специальности:"
            next_state = UserState.ENTERING_WORKER_COUNT.value
        else:  # job_search
            next_text = "На какой период требуется работа?"
            next_state = UserState.ENTERING_WORK_PERIOD.value

        keyboard = [[InlineKeyboardButton("◀️ Начать заново", callback_data="back_to_firm_type")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(next_text, reply_markup=reply_markup)
        self.db.update_user_state(user_id, next_state)

    async def process_worker_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка количества работников"""
        user_id = update.effective_user.id
        worker_count = update.message.text

        # Сохраняем количество работников
        session_data = self.db.get_session_data(user_id)
        session_data['worker_count'] = worker_count
        self.db.save_session_data(user_id, session_data)

        keyboard = [[InlineKeyboardButton("◀️ Начать заново", callback_data="back_to_firm_type")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "На какой период времени требуются сотрудники?",
            reply_markup=reply_markup
        )
        self.db.update_user_state(user_id, UserState.ENTERING_WORK_PERIOD.value)

    async def process_work_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка периода работы"""
        user_id = update.effective_user.id
        work_period = update.message.text

        # Сохраняем период работы
        session_data = self.db.get_session_data(user_id)
        session_data['work_period'] = work_period
        self.db.save_session_data(user_id, session_data)

        keyboard = [[InlineKeyboardButton("◀️ Начать заново", callback_data="back_to_firm_type")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Опишите место работы, характер, условия:",
            reply_markup=reply_markup
        )
        self.db.update_user_state(user_id, UserState.ENTERING_WORK_CONDITIONS.value)

    async def process_work_conditions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка условий работы"""
        user_id = update.effective_user.id
        work_conditions = update.message.text

        # Сохраняем условия работы
        session_data = self.db.get_session_data(user_id)
        session_data['work_conditions'] = work_conditions
        self.db.save_session_data(user_id, session_data)

        keyboard = [[InlineKeyboardButton("◀️ Начать заново", callback_data="back_to_firm_type")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Опишите требования к претендентам:",
            reply_markup=reply_markup
        )
        self.db.update_user_state(user_id, UserState.ENTERING_REQUIREMENTS.value)

    async def process_requirements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка требований"""
        user_id = update.effective_user.id
        requirements = update.message.text

        # Сохраняем требования
        session_data = self.db.get_session_data(user_id)
        session_data['requirements'] = requirements
        self.db.save_session_data(user_id, session_data)

        keyboard = [[InlineKeyboardButton("◀️ Начать заново", callback_data="back_to_firm_type")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Укажите размер зп и условия:",
            reply_markup=reply_markup
        )
        self.db.update_user_state(user_id, UserState.ENTERING_SALARY.value)

    async def process_salary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка зарплаты"""
        user_id = update.effective_user.id
        salary = update.message.text

        # Сохраняем зарплату
        session_data = self.db.get_session_data(user_id)
        session_data['salary'] = salary
        self.db.save_session_data(user_id, session_data)

        # Переходим к вводу контактов
        keyboard = [
            [KeyboardButton("📞 Поделиться вашим номером телефона", request_contact=True)],
            [InlineKeyboardButton("◀️ Начать заново", callback_data="back_to_firm_type")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard[1:])

        await update.message.reply_text(
            "Укажите ваш(и) контакт(ы), либо нажмите на кнопку для автоматической отправки:",
            reply_markup=reply_markup
        )

        # Также отправляем клавиатуру с кнопкой контакта
        contact_markup = ReplyKeyboardMarkup([[keyboard[0][0]]], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Или нажмите кнопку ниже:",
            reply_markup=contact_markup
        )

        self.db.update_user_state(user_id, UserState.ENTERING_CONTACTS.value)

    async def process_contacts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка контактов"""
        user_id = update.effective_user.id
        contacts = update.message.text

        # Сохраняем контакты
        session_data = self.db.get_session_data(user_id)
        session_data['contacts'] = contacts
        self.db.save_session_data(user_id, session_data)

        await self.review_publication(update, context)

    async def review_publication(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Предварительный просмотр публикации"""
        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)

        # Форматируем текст публикации
        publication_text = self.format_publication_text(session_data)

        # Проверяем на стоп-слова
        has_stop_words, stop_words = self.filter_service.check_text(publication_text)

        if has_stop_words:
            # Убираем клавиатуру с кнопкой контакта
            await update.message.reply_text(
                MESSAGES["stop_words_found"],
                reply_markup=ReplyKeyboardRemove()
            )

            keyboard = [[InlineKeyboardButton("Заполнить объявление заново", callback_data="back_to_firm_type")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"Постарайтесь избегать СТОП-СЛОВ: {stop_words} ",
                reply_markup=reply_markup
            )
            return

        # Показываем предварительный просмотр
        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать", callback_data="back_to_firm_type")],
            [InlineKeyboardButton("✅ Продолжить", callback_data="review_publication")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Предварительный просмотр:\n\n{publication_text}",
            reply_markup=ReplyKeyboardRemove()
        )

        await update.message.reply_text(
            "Проверьте публикацию:",
            reply_markup=reply_markup
        )

        self.db.update_user_state(user_id, UserState.REVIEWING_POST.value)

    async def show_publication_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать варианты публикации"""
        query = update.callback_query
        await query.answer()

        keyboard = [
            [InlineKeyboardButton("📤 Опубликовать сразу", callback_data="publish_immediately")],
            #[InlineKeyboardButton("⏰ Отложенная публикация", callback_data="delayed_publication")],
            [InlineKeyboardButton("🔄 Автопостинг", callback_data="auto_posting")],
            [InlineKeyboardButton("🏠 Главная", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )

    async def publish_immediately(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Опубликовать сразу"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)

        # Определяем стоимость ПРАВИЛЬНО в зависимости от типа публикации
        pub_type = session_data.get('publication_type', 'advertisement')
        if pub_type == 'advertisement':
            cost = 160  # Реклама стоит 160 рублей
        else:  # job_offer или job_search
            cost = 100  # Объявления о работе стоят 100 рублей

        logger.info(f"Публикация типа {pub_type}, стоимость: {cost}")

        # Проверяем баланс (если не админ)
        if not self.db.is_user_admin(user_id):
            if not self.db.check_balance(user_id, cost):
                await query.edit_message_text(
                    f"Недостаточно средств. Требуется: {cost} рублей",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🛒 Пополнить баланс", callback_data="menu_магазин")
                    ]])
                )
                return

            # Списываем деньги
            self.db.update_balance(user_id, -cost)
            logger.info(f"Списано {cost} рублей с баланса пользователя {user_id}")

        # Форматируем и публикуем
        publication_text = self.format_publication_text(session_data)

        try:
            # Определяем изображение в зависимости от типа публикации
            image_path = self._get_image_path_for_publication(pub_type)

            # Отправляем в группу
            bot = context.bot
            group_id = context.bot_data.get('group_id', -1002850839936)

            # Проверяем наличие изображения
            if os.path.exists(image_path):
                # Отправляем сообщение с изображением в группу
                with open(image_path, 'rb') as photo:
                    message = await bot.send_photo(
                        chat_id=group_id,
                        photo=photo,
                        caption=publication_text,
                        parse_mode='HTML'
                    )
            else:
                # Если изображение не найдено, отправляем только текст
                logger.warning(f"Изображение {image_path} не найдено. Отправляем только текст")
                message = await bot.send_message(
                    chat_id=group_id,
                    text=publication_text,
                    parse_mode='HTML'
                )

            # Сохраняем в БД
            publication_id = self.db.create_publication(
                user_id=user_id,
                pub_type=pub_type,
                text=publication_text,
                cost=cost,
                firm_type=session_data.get('firm_type'),
                firm_name=session_data.get('firm_name')
            )

            self.db.update_publication_status(
                publication_id=publication_id,
                status='published',
                message_id=message.message_id
            )

            # Уведомляем пользователя
            pub_type_text = "рекламное объявление" if pub_type == 'advertisement' else "объявление о работе"
            time_str = datetime.now().strftime("%d.%m.%Y в %H:%M")
            keyboard = [[InlineKeyboardButton("🏠 Главная", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"✅ Ваше {pub_type_text} опубликовано {time_str}",
                reply_markup=reply_markup
            )

            # Очищаем сессию
            self.db.clear_session_data(user_id)
            self.db.update_user_state(user_id, UserState.IDLE.value)

        except Exception as e:
            logger.error(f"Ошибка публикации: {e}")
            await query.edit_message_text(
                "❌ Ошибка при публикации. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главная", callback_data="main_menu")
                ]])
            )

    # АВТОПОСТИНГ - полная реализация согласно ТЗ
    async def auto_posting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Автопостинг - выбор периодичности"""
        query = update.callback_query

        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)
        pub_type = session_data.get('publication_type', 'advertisement')
        await query.answer()

        keyboard = [
            [InlineKeyboardButton("Раз в сутки", callback_data="frequency_daily")],
            [InlineKeyboardButton("Раз в неделю", callback_data="frequency_weekly")],
            [InlineKeyboardButton("◀️ Назад", callback_data="review_publication")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        typecal_text = "должно публиковаться рекламное объявление" if pub_type == 'advertisement' else "должно публиковаться объявление о работе"
        await query.edit_message_text(
            f"С какой периодичностью {typecal_text}?",
            reply_markup=reply_markup
        )

        user_id = update.effective_user.id
        self.db.update_user_state(user_id, UserState.CHOOSING_AUTOPOST_FREQUENCY.value)

    async def process_frequency_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора периодичности"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        frequency = query.data.split("_")[1]  # daily или weekly

        # Сохраняем частоту в сессии
        session_data = self.db.get_session_data(user_id)
        session_data['autopost_frequency'] = frequency
        self.db.save_session_data(user_id, session_data)

        if frequency == "weekly":
            # Показываем выбор дня недели
            keyboard = [
                [InlineKeyboardButton("Понедельник", callback_data="weekday_0")],
                [InlineKeyboardButton("Вторник", callback_data="weekday_1")],
                [InlineKeyboardButton("Среда", callback_data="weekday_2")],
                [InlineKeyboardButton("Четверг", callback_data="weekday_3")],
                [InlineKeyboardButton("Пятница", callback_data="weekday_4")],
                [InlineKeyboardButton("Суббота", callback_data="weekday_5")],
                [InlineKeyboardButton("Воскресенье", callback_data="weekday_6")],
                [InlineKeyboardButton("◀️ Назад", callback_data="auto_posting")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            pub_type = session_data.get('publication_type', 'advertisement')
            typecal_text = "должно публиковаться рекламное объявление" if pub_type == 'advertisement' else "должно публиковаться объявление о работе"
            await query.edit_message_text(
                f"Выберите день недели в который {typecal_text}:",
                reply_markup=reply_markup
            )
            self.db.update_user_state(user_id, UserState.CHOOSING_WEEKDAY.value)
        else:
            # Для ежедневной публикации сразу переходим к вводу времени
            await self.ask_for_time(query, context)

    async def process_weekday_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора дня недели"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        weekday = int(query.data.split("_")[1])

        # Сохраняем день недели в сессии
        session_data = self.db.get_session_data(user_id)
        session_data['autopost_weekday'] = weekday
        self.db.save_session_data(user_id, session_data)

        await self.ask_for_time(query, context)

    async def ask_for_time(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Запрос времени для автопостинга"""
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="auto_posting")]]
        reply_markup = InlineKeyboardMarkup(keyboard)


        user_id = query.from_user.id
        self.db.update_user_state(user_id, UserState.ENTERING_TIME.value)

        session_data = self.db.get_session_data(user_id)
        pub_type = session_data.get('publication_type', 'advertisement')
        typecal_text = "должно публиковаться рекламное объявление" if pub_type == 'advertisement' else "должно публиковаться объявление о работе"

        await query.edit_message_text(
        f"Введите время в которое {typecal_text} в формате ЧЧ:ММ",
        reply_markup=reply_markup
    )



    async def back_to_time_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к вводу времени"""
        query = update.callback_query
        await query.answer()

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="auto_posting")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        user_id = update.effective_user.id
        self.db.update_user_state(user_id, UserState.ENTERING_TIME.value)

        session_data = self.db.get_session_data(user_id)
        pub_type = session_data.get('publication_type', 'advertisement')
        typecal_text = "должно публиковаться рекламное объявление" if pub_type == 'advertisement' else "должно публиковаться объявление о работе"

        await query.edit_message_text(
            f"Введите время в которое {typecal_text} в формате ЧЧ:ММ",
            reply_markup=reply_markup
        )

    async def process_time_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода времени"""
        user_id = update.effective_user.id
        time_text = update.message.text.strip()

        # Валидация времени
        if not FORMATS["time"].match(time_text):
            await update.message.reply_text(
                MESSAGES["invalid_time_format"]
            )
            return

        # Сохраняем время в сессии
        session_data = self.db.get_session_data(user_id)
        session_data['autopost_time'] = time_text
        self.db.save_session_data(user_id, session_data)

        # Показываем информацию о ценах и запрашиваем количество повторений
        pub_type = session_data.get('publication_type', 'advertisement')
        balance = self.db.get_user_balance(user_id)

        # Пробую подставить в текст Дней, недель и обьявление рекламу
        daynedel = session_data.get('autopost_frequency')
        if session_data.get('autopost_weekday') == 0:
            kogda_text = "в понедельник"
        else:
            if session_data.get('autopost_weekday') == 1:
                kogda_text = "во вторник"
            else:
                if session_data.get('autopost_weekday') == 2:
                    kogda_text = "в среду"
                else:
                    if session_data.get('autopost_weekday') == 3:
                        kogda_text = "в четверг"
                    else:
                        if session_data.get('autopost_weekday') == 4:
                            kogda_text = "в пятницу"
                        else:
                            if session_data.get('autopost_weekday') == 5:
                                kogda_text = "в субботу"
                            else:
                                if session_data.get('autopost_weekday') == 6:
                                    kogda_text = "в воскресенье"
        publication_text = "должна опубликоваться реклама" if pub_type == "advertisement" else "должно опубликоваться объявление"


        if pub_type == 'advertisement':
            pricing_text = """Публикация Рекламы на платной основе.
1 размещение в группе - 160 ₽

Также есть возможность пакетного размещения с 20% скидкой:
2 размещения - 256 ₽ (вместо 320 ₽)
3 размещения - 384 ₽ (вместо 480 ₽)
5 размещений - 640 ₽ (вместо 800 ₽)
7 размещений - 896 ₽ (вместо 1120 ₽)
10 размещений - 1280 ₽ (вместо 1600 ₽)
15 размещений - 1920 ₽ (вместо 2400 ₽)
30 размещений - 3840₽ (вместо 4800 ₽)"""
        else:
            pricing_text = """Публикация объявлений на платной основе.
1 размещение в группе - 100 ₽

Также есть возможность пакетного размещения с 20% скидкой:
2 публикации - 160₽ (вместо 200₽)
3 публикации - 240 ₽ (вместо 300 ₽)
5 публикации - 400 ₽ (вместо 500 ₽)
7 публикации - 560 ₽ (вместо 700 ₽)
10 публикации - 800 ₽ (вместо 1000 ₽)
15 публикации - 1200 ₽ (вместо 1500 ₽)
30 публикации - 2400 ₽ (вместо 3000 ₽)"""

        if daynedel == "daily":
            text = f"Ваш баланс: {int(balance)} рублей. Введите сколько дней подряд {publication_text}  \n\n{pricing_text}"
        else:
            text = f"Ваш баланс: {int(balance)} рублей. Введите сколько недель подряд раз {kogda_text} {publication_text}  \n\n{pricing_text}"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_time_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)
        self.db.update_user_state(user_id, UserState.ENTERING_REPETITIONS.value)

    async def back_to_repetitions_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к вводу количества повторений"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)
        pub_type = session_data.get('publication_type', 'advertisement')
        balance = self.db.get_user_balance(user_id)

        # Пробую подставить в текст Дней, недель и обьявление рекламу
        daynedel = session_data.get('autopost_frequency')
        if session_data.get('autopost_weekday') == 0:
            kogda_text = "в понедельник"
        else:
            if session_data.get('autopost_weekday') == 1:
                kogda_text = "во вторник"
            else:
                if session_data.get('autopost_weekday') == 2:
                    kogda_text = "в среду"
                else:
                    if session_data.get('autopost_weekday') == 3:
                        kogda_text = "в четверг"
                    else:
                        if session_data.get('autopost_weekday') == 4:
                            kogda_text = "в пятницу"
                        else:
                            if session_data.get('autopost_weekday') == 5:
                                kogda_text = "в субботу"
                            else:
                                if session_data.get('autopost_weekday') == 6:
                                    kogda_text = "в воскресенье"
        publication_text = "должна опубликоваться реклама" if pub_type == "advertisement" else "должно опубликоваться объявление"

        if pub_type == 'advertisement':
            pricing_text = """Публикация Рекламы на платной основе.
1 размещение в группе - 160 ₽

Также есть возможность пакетного размещения с 20% скидкой:
2 размещения - 256 ₽ (вместо 320 ₽)
3 размещения - 384 ₽ (вместо 480 ₽)
5 размещений - 640 ₽ (вместо 800 ₽)
7 размещений - 896 ₽ (вместо 1120 ₽)
10 размещений - 1280 ₽ (вместо 1600 ₽)
15 размещений - 1920 ₽ (вместо 2400 ₽)
30 размещений - 3840₽ (вместо 4800 ₽)"""
        else:
            pricing_text = """Публикация объявлений на платной основе.
1 размещение в группе - 100 ₽

Также есть возможность пакетного размещения с 20% скидкой:
2 публикации - 160₽ (вместо 200₽)
3 публикации - 240 ₽ (вместо 300 ₽)
5 публикации - 400 ₽ (вместо 500 ₽)
7 публикации - 560 ₽ (вместо 700 ₽)
10 публикации - 800 ₽ (вместо 1000 ₽)
15 публикации - 1200 ₽ (вместо 1500 ₽)
30 публикации - 2400 ₽ (вместо 3000 ₽)"""

        if daynedel == "daily":
            text = f"Ваш баланс: {int(balance)} рублей. Введите сколько дней подряд {publication_text}  \n\n{pricing_text}"
        else:
            text = f"Ваш баланс: {int(balance)} рублей. Введите сколько недель подряд раз {kogda_text} {publication_text}  \n\n{pricing_text}"


        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_time_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)
        self.db.update_user_state(user_id, UserState.ENTERING_REPETITIONS.value)

    async def process_repetitions_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода количества повторений"""
        user_id = update.effective_user.id
        repetitions_text = update.message.text.strip()

        try:
            repetitions = int(repetitions_text)
            if repetitions < 1 or repetitions > 30:
                raise ValueError("Количество должно быть от 1 до 30")
        except ValueError:
            await update.message.reply_text(
                "❌ Некорректное количество. Введите число от 1 до 30."
            )
            return

        session_data = self.db.get_session_data(user_id)
        pub_type = session_data.get('publication_type', 'advertisement')

        # Рассчитываем стоимость с учетом пакетных скидок
        pricing_key = "advertisement" if pub_type == 'advertisement' else "job"
        if repetitions in PACKAGE_PRICING[pricing_key]:
            total_cost = PACKAGE_PRICING[pricing_key][repetitions]
        else:
            # Применяем скидку 20% для количества >= 2
            base_price = PACKAGE_PRICING[pricing_key][1]
            if repetitions >= 2:
                total_cost = base_price * repetitions * 0.8
            else:
                total_cost = base_price

        # Проверяем баланс (если не админ)
        if not self.db.is_user_admin(user_id):
            if not self.db.check_balance(user_id, total_cost):
                balance = self.db.get_user_balance(user_id)

                keyboard = [
                    [InlineKeyboardButton("Редактировать количество", callback_data="back_to_repetitions")],
                    [InlineKeyboardButton("🛒 Магазин", callback_data="menu_магазин")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    f"У вас недостаточно средств на балансе для такого количества публикаций. "
                    f"Ваш баланс {int(balance)} рублей. Введите корректное кол-во публикаций "
                    f"или перейдите в магазин чтобы пополнить баланс",
                    reply_markup=reply_markup
                )
                return

        # Сохраняем данные и планируем автопостинг
        session_data['autopost_repetitions'] = repetitions
        session_data['autopost_cost'] = total_cost
        self.db.save_session_data(user_id, session_data)

        await self.schedule_autopost(update, context)

    async def schedule_autopost(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Планирование автопостинга"""
        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)

        frequency = session_data.get('autopost_frequency')
        time_str = session_data.get('autopost_time')
        repetitions = session_data.get('autopost_repetitions')
        total_cost = session_data.get('autopost_cost')
        weekday = session_data.get('autopost_weekday')
        pub_type = session_data.get('publication_type', 'advertisement')

        # Списываем деньги (если не админ)
        if not self.db.is_user_admin(user_id):
            self.db.update_balance(user_id, -total_cost)
            logger.info(f"Списано {total_cost} рублей за автопостинг с баланса пользователя {user_id}")

        # Планируем публикации через scheduler
        publication_text = self.format_publication_text(session_data)

        try:
            if self.scheduler:
                job_id = await self.scheduler.schedule_recurring_post(
                    user_id=user_id,
                    text=publication_text,
                    frequency=frequency,
                    time_str=time_str,
                    day_of_week=weekday,
                    repetitions=repetitions,
                    pub_type=pub_type
                )
                logger.info(f"Запланирован автопостинг с ID {job_id}")
        except Exception as e:
            logger.error(f"Ошибка планирования автопостинга: {e}")

        # Уведомляем пользователя
        frequency_text = "сутки" if frequency == "daily" else "неделю"
        pub_type_text = "Ваше рекламное объявление" if pub_type == "advertisement" else "Ваше объявление о работе"

        if session_data.get('autopost_weekday') == 0:
            kogda = "каждый понедельник"
        else:
            if session_data.get('autopost_weekday') == 1:
                kogda = "каждый вторник"
            else:
                if session_data.get('autopost_weekday') == 2:
                    kogda = "каждую среду"
                else:
                    if session_data.get('autopost_weekday') == 3:
                        kogda = "каждый четверг"
                    else:
                        if session_data.get('autopost_weekday') == 4:
                            kogda = "каждую пятницу"
                        else:
                            if session_data.get('autopost_weekday') == 5:
                                kogda = "каждую субботу"
                            else:
                                if session_data.get('autopost_weekday') == 6:
                                    kogda = "каждое воскресенье"

        keyboard = [[InlineKeyboardButton("🏠 Главная", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if frequency == "daily":
            await update.message.reply_text(
                f"✅ {pub_type_text} будет публиковаться раз в {frequency_text}\n {repetitions} сутки(ок) подряд в {time_str}",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"✅ {pub_type_text} будет публиковаться раз в {frequency_text}\n {kogda} {repetitions} недель(и) подряд в {time_str}",
                reply_markup=reply_markup
            )



        # Очищаем сессию
        self.db.clear_session_data(user_id)
        self.db.update_user_state(user_id, UserState.IDLE.value)

    # ОТЛОЖЕННАЯ ПУБЛИКАЦИЯ - полная реализация согласно ТЗ
    async def delayed_publication(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отложенная публикация - управление слотами"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)
        pub_type = session_data.get('publication_type', 'advertisement')
        balance = self.db.get_user_balance(user_id)

        logger.info(f"Отложенная публикация для пользователя {user_id}, тип: {pub_type}, баланс: {balance}")

        # ИСПРАВЛЕНО: Правильные требования к балансу согласно ТЗ
        available_slots = []
        if self.db.is_user_admin(user_id):
            available_slots = [1, 2, 3]
            logger.info(f"Пользователь {user_id} - админ, доступны все слоты")
        else:
            # Определяем доступные слоты в зависимости от типа публикации и баланса
            balance_requirements = DELAYED_BALANCE_REQUIREMENTS.get(pub_type, DELAYED_BALANCE_REQUIREMENTS['job'])

            if balance >= balance_requirements[3]:
                available_slots = [1, 2, 3]
            elif balance >= balance_requirements[2]:
                available_slots = [1, 2]
            elif balance >= balance_requirements[1]:
                available_slots = [1]

            logger.info(f"Для типа {pub_type} при балансе {balance} доступны слоты: {available_slots}")

        # Получаем сохраненные слоты из сессии
        delayed_slots = session_data.get('delayed_slots', {})

        keyboard = []

        # Добавляем кнопки автопубликации
        for slot_num in range(1, 4):
            if slot_num in available_slots:
                slot_text = delayed_slots.get(f'slot_{slot_num}', '')
                if slot_text:
                    button_text = f"Автопубликация {slot_num} - {slot_text}"
                else:
                    button_text = f"Автопубликация {slot_num}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"delayed_slot_{slot_num}")])

        # Кнопки управления
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="review_publication")])

        # Кнопка "Опубликовать" доступна только если есть хотя бы один заполненный слот
        if delayed_slots:
            keyboard.append([InlineKeyboardButton("✅ Опубликовать", callback_data="confirm_delayed_publication")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Выберите время для автопубликации:",
            reply_markup=reply_markup
        )

        self.db.update_user_state(user_id, UserState.CHOOSING_DELAYED_SLOT.value)

    async def process_delayed_slot_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора слота для отложенной публикации"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        slot_num = int(query.data.split("_")[-1])

        logger.info(f"Пользователь {user_id} выбрал слот {slot_num}")

        # Сохраняем номер выбранного слота
        session_data = self.db.get_session_data(user_id)
        session_data['current_delayed_slot'] = slot_num
        self.db.save_session_data(user_id, session_data)

        # Проверяем, есть ли уже время в этом слоте
        delayed_slots = session_data.get('delayed_slots', {})
        current_time = delayed_slots.get(f'slot_{slot_num}', '')

        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="delayed_publication")]
        ]

        if current_time:
            keyboard.insert(0, [
                InlineKeyboardButton("🗑️ Убрать с автопубликации", callback_data=f"remove_delayed_slot_{slot_num}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Пришлите время для автопубликации, в формате: дд.мм.гггг чч:мм",
            reply_markup=reply_markup
        )

        self.db.update_user_state(user_id, UserState.ENTERING_DELAYED_DATETIME.value)

    async def process_delayed_datetime_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕНО: Обработка ввода даты и времени для отложенной публикации"""
        user_id = update.effective_user.id
        datetime_text = update.message.text.strip()

        logger.info(f"Обработка ввода времени '{datetime_text}' от пользователя {user_id}")

        # Валидация формата даты и времени
        if not FORMATS["datetime"].match(datetime_text):
            logger.warning(f"Некорректный формат даты: {datetime_text}")
            keyboard = [
                [InlineKeyboardButton("✏️ Внести изменения", callback_data="retry_datetime_input")],
                [InlineKeyboardButton("❌ Отменить", callback_data="delayed_publication")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                MESSAGES["invalid_datetime_format"],
                reply_markup=reply_markup
            )
            return

        try:
            # ИСПРАВЛЕНО: Правильный парсинг даты и времени
            date_part, time_part = datetime_text.split(' ')
            day, month, year = map(int, date_part.split('.'))
            hour, minute = map(int, time_part.split(':'))

            scheduled_datetime = datetime(year, month, day, hour, minute)

            # Проверяем, что дата в будущем
            if scheduled_datetime <= datetime.now():
                await update.message.reply_text(
                    "❌ Указанное время должно быть в будущем. Попробуйте снова."
                )
                return

            logger.info(f"Дата успешно распознана: {scheduled_datetime}")

        except ValueError as e:
            logger.error(f"Ошибка парсинга даты {datetime_text}: {e}")
            keyboard = [
                [InlineKeyboardButton("✏️ Внести изменения", callback_data="retry_datetime_input")],
                [InlineKeyboardButton("❌ Отменить", callback_data="delayed_publication")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                MESSAGES["invalid_datetime_format"],
                reply_markup=reply_markup
            )
            return

        # Сохраняем время в соответствующий слот
        session_data = self.db.get_session_data(user_id)
        slot_num = session_data.get('current_delayed_slot', 1)

        if 'delayed_slots' not in session_data:
            session_data['delayed_slots'] = {}

        session_data['delayed_slots'][f'slot_{slot_num}'] = datetime_text
        self.db.save_session_data(user_id, session_data)

        logger.info(f"Время {datetime_text} сохранено в слот {slot_num}")

        # Возвращаемся к выбору слотов
        await self.delayed_publication(update, context)

    async def retry_datetime_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕНО: Повторный ввод даты и времени"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)
        slot_num = session_data.get('current_delayed_slot', 1)

        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="delayed_publication")],
            [InlineKeyboardButton("🗑️ Убрать с автопубликации", callback_data=f"remove_delayed_slot_{slot_num}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Пришлите время для автопубликации, в формате: дд.мм.гггг чч:мм",
            reply_markup=reply_markup
        )

        self.db.update_user_state(user_id, UserState.ENTERING_DELAYED_DATETIME.value)

    async def remove_delayed_slot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление времени из слота отложенной публикации"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        slot_num = int(query.data.split("_")[-1])

        # Удаляем время из слота
        session_data = self.db.get_session_data(user_id)
        delayed_slots = session_data.get('delayed_slots', {})

        if f'slot_{slot_num}' in delayed_slots:
            del delayed_slots[f'slot_{slot_num}']
            session_data['delayed_slots'] = delayed_slots
            self.db.save_session_data(user_id, session_data)

        # Возвращаемся к выбору слотов
        await self.delayed_publication(update, context)

    async def confirm_delayed_publication(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕНО: Подтверждение и выполнение отложенной публикации"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        session_data = self.db.get_session_data(user_id)
        pub_type = session_data.get('publication_type', 'advertisement')
        delayed_slots = session_data.get('delayed_slots', {})

        if not delayed_slots:
            await query.edit_message_text(
                "❌ Нет запланированных публикаций",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="delayed_publication")
                ]])
            )
            return

        # ИСПРАВЛЕНО: Правильный расчет стоимости согласно ТЗ
        num_slots = len(delayed_slots)

        # Расчет стоимости по количеству слотов
        if pub_type == 'advertisement':
            if num_slots == 1:
                cost = 160
            elif num_slots == 2:
                cost = 256
            else:  # num_slots == 3
                cost = 384
        else:  # job_offer или job_search
            if num_slots == 1:
                cost = 100
            elif num_slots == 2:
                cost = 160
            else:  # num_slots == 3
                cost = 240

        logger.info(f"Стоимость отложенной публикации: {cost} за {num_slots} слотов")

        # Проверяем баланс (если не админ)
        if not self.db.is_user_admin(user_id):
            if not self.db.check_balance(user_id, cost):
                await query.edit_message_text(
                    f"❌ Недостаточно средств. Требуется: {cost} рублей",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🛒 Пополнить баланс", callback_data="menu_магазин")
                    ]])
                )
                return

            # Списываем деньги
            self.db.update_balance(user_id, -cost)
            logger.info(f"Списано {cost} рублей за отложенную публикацию с баланса пользователя {user_id}")

        # Планируем публикации
        publication_text = self.format_publication_text(session_data)
        scheduled_list = []

        for slot_key, datetime_str in delayed_slots.items():
            slot_num = slot_key.split('_')[1]

            try:
                # Парсим дату и время
                date_part, time_part = datetime_str.split(' ')
                day, month, year = map(int, date_part.split('.'))
                hour, minute = map(int, time_part.split(':'))
                scheduled_datetime = datetime(year, month, day, hour, minute)

                # Планируем через scheduler
                if self.scheduler:
                    job_id = await self.scheduler.schedule_single_post(
                        user_id=user_id,
                        text=publication_text,
                        scheduled_time=scheduled_datetime,
                        pub_type=pub_type
                    )
                    logger.info(f"Запланирована отложенная публикация с ID {job_id}")

                scheduled_list.append(f"{slot_num}) {datetime_str}")

            except Exception as e:
                logger.error(f"Ошибка планирования отложенной публикации: {e}")

        # Уведомляем пользователя
        pub_type_text = "реклама" if pub_type == 'advertisement' else "объявление"
        schedule_text = "\n".join(scheduled_list)

        keyboard = [[InlineKeyboardButton("🏠 Главная", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"✅ Ваша {pub_type_text} будет опубликована:\n{schedule_text}",
            reply_markup=reply_markup
        )

        # Очищаем сессию
        self.db.clear_session_data(user_id)
        self.db.update_user_state(user_id, UserState.IDLE.value)

    # Дополнительные методы обработки ошибок
    async def handle_insufficient_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка недостаточного баланса"""
        query = update.callback_query
        await query.answer()

        keyboard = [
            [InlineKeyboardButton("🛒 Магазин", callback_data="menu_магазин")],
            [InlineKeyboardButton("🏠 Главная", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Недостаточно средств на балансе.",
            reply_markup=reply_markup
        )

    async def _send_error_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, error_text: str = None):
        """Унифицированная отправка сообщений об ошибках"""
        text = error_text or ERROR_MESSAGES["general_error"]

        keyboard = [[InlineKeyboardButton("🏠 Главная", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения об ошибке: {e}")

    def _get_image_path_for_publication(self, pub_type: str) -> str:
        """
        Получить путь к изображению в зависимости от типа публикации

        Args:
            pub_type: Тип публикации

        Returns:
            str: Путь к файлу изображения
        """
        if pub_type == "advertisement":
            return "picture/reklama.jpg"
        elif pub_type == "job_offer":
            return "picture/gotovoe_poisk_rabotnikov.jpg"
        elif pub_type == "job_search":
            return "picture/gotovoe_poisk_vakansiy.jpg"
        else:
            # Если тип неизвестен, используем рекламу по умолчанию
            return "picture/reklama.jpg"

    def format_publication_text(self, session_data: dict) -> str:
        """Форматирование текста публикации"""
        pub_type = session_data.get('publication_type')

        if pub_type == 'advertisement':
            return f"""📢 {session_data.get('firm_type', '')} "{session_data.get('firm_name', '')}"

{session_data.get('ad_text', '')}

📞 Контакты: {session_data.get('contacts', '')}

Хочешь тоже разместить свое объявление или рекламу в группу?
Пиши @RABOTA100_150_BOT"""

        elif pub_type == 'job_offer':
            return f"""💼 {session_data.get('firm_type', '')} "{session_data.get('firm_name', '')}"

🎯 Вакансия: {session_data.get('job_title', '')}
👥 Количество сотрудников: {session_data.get('worker_count', '')}
📅 Период работы: {session_data.get('work_period', '')}
🏢 Условия: {session_data.get('work_conditions', '')}
📋 Требования: {session_data.get('requirements', '')}
💰 Зарплата: {session_data.get('salary', '')}

📞 Контакты: {session_data.get('contacts', '')}

Хочешь тоже разместить свое объявление или рекламу в группу?
Пиши @RABOTA100_150_BOT"""


        else:  # job_search
            return f"""🔍 {session_data.get('firm_type', '')} "{session_data.get('firm_name', '')}"

💼 Ищу работу: {session_data.get('job_title', '')}
📅 Период: {session_data.get('work_period', '')}
🏢 Предпочитаемые условия: {session_data.get('work_conditions', '')}
📋 Требования к работодателю: {session_data.get('requirements', '')}
💰 Желаемая зарплата: {session_data.get('salary', '')}

📞 Контакты: {session_data.get('contacts', '')}

Хочешь тоже разместить свое объявление или рекламу в группу?
Пиши @RABOTA100_150_BOT"""
