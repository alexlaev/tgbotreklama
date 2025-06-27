from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

class AdminHandlers:
    """Обработчики для администраторов"""

    def __init__(self, db_manager):
        self.db = db_manager

    async def admin_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Стартовое сообщение для админа"""
        welcome_text = "🔧 Добро пожаловать в административную панель!\nВыберите действие:"

        keyboard = [
            [InlineKeyboardButton("Проверить список стоп слов", callback_data="admin_проверить_список_стоп_слов")],
            [InlineKeyboardButton("Добавить стоп слова", callback_data="admin_добавить_стоп_слова")],
            [InlineKeyboardButton("Очистить список стоп слов", callback_data="admin_очистить_список_стоп_слов")],
            [InlineKeyboardButton("Создать публикацию", callback_data="admin_создать_публикацию")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def show_stop_words(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список стоп-слов"""
        query = update.callback_query
        await query.answer()

        stop_words = self.db.get_all_stop_words()
        if stop_words:
            words_text = "📝 Список стоп-слов:\n\n" + "\n".join(f"• {word}" for word in stop_words)
        else:
            words_text = "📝 Список стоп-слов пуст"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(words_text, reply_markup=reply_markup)

    async def add_stop_words_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрос на ввод стоп-слов"""
        query = update.callback_query
        await query.answer()

        text = "📝 Введите одно или несколько стоп-слов через запятую:"
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

        # Устанавливаем состояние ожидания ввода стоп-слов
        self.db.update_user_state(update.effective_user.id, "waiting_stop_words")
        return "WAITING_STOP_WORDS"

    async def process_stop_words(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка введенных стоп-слов"""
        user_id = update.effective_user.id
        text = update.message.text

        # Разбираем введенные слова
        words = [word.strip() for word in text.split(",") if word.strip()]

        if words:
            self.db.add_stop_words(words, user_id)
            response = f"✅ Стоп-слова добавлены: {', '.join(words)}"
        else:
            response = "❌ Не удалось распознать стоп-слова"

        # Возвращаем пользователя в главное меню
        welcome_text = "🔧 Добро пожаловать в административную панель!\nВыберите действие:"
        keyboard = [
            [InlineKeyboardButton("Проверить список стоп слов", callback_data="admin_проверить_список_стоп_слов")],
            [InlineKeyboardButton("Добавить стоп слова", callback_data="admin_добавить_стоп_слова")],
            [InlineKeyboardButton("Очистить список стоп слов", callback_data="admin_очистить_список_стоп_слов")],
            [InlineKeyboardButton("Создать публикацию", callback_data="admin_создать_публикацию")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(response)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

        self.db.update_user_state(user_id, "idle")
        return ConversationHandler.END

    async def clear_stop_words(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Очистить все стоп-слова"""
        query = update.callback_query
        await query.answer()

        self.db.clear_stop_words()
        text = "🗑️ Список стоп-слов очищен"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def admin_create_publication(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переход к созданию публикации (переход в главное меню)"""
        query = update.callback_query
        await query.answer()

        # Импортируем здесь, чтобы избежать циклического импорта
        from .user_handlers import UserHandlers
        user_handlers = UserHandlers(self.db)

        # Переводим админа в главное меню пользователя
        await user_handlers.show_main_menu(update, context)

    async def admin_back_to_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат в главное меню админа"""
        query = update.callback_query
        await query.answer()

        welcome_text = "🔧 Добро пожаловать в административную панель!\nВыберите действие:"
        keyboard = [
            [InlineKeyboardButton("Проверить список стоп слов", callback_data="admin_проверить_список_стоп_слов")],
            [InlineKeyboardButton("Добавить стоп слова", callback_data="admin_добавить_стоп_слова")],
            [InlineKeyboardButton("Очистить список стоп слов", callback_data="admin_очистить_список_стоп_слов")],
            [InlineKeyboardButton("Создать публикацию", callback_data="admin_создать_публикацию")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(welcome_text, reply_markup=reply_markup)

    async def admin_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена текущей операции"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        self.db.update_user_state(user_id, "idle")

        await self.admin_back_to_main(update, context)
        return ConversationHandler.END
