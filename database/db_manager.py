# Исправленный файл database/db_manager.py

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
import json
import logging
from datetime import datetime

from .models import Base, User, Balance, Publication, Payment, ScheduledPost, StopWord, UserSession

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Менеджер для работы с базой данных"""

    def __init__(self, database_url: str, echo: bool = False):
        self.engine = create_engine(database_url, echo=echo)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Создание всех таблиц"""
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Session:
        """Контекстный менеджер для получения сессии"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Методы для работы с пользователями
    def get_or_create_user(self, user_id: int, username: str = None,
                           first_name: str = None, last_name: str = None) -> User:
        """Получить или создать пользователя"""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if not user:
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                session.flush()

                # Создаем баланс для нового пользователя
                balance = Balance(user_id=user_id, amount=0.0)
                session.add(balance)
            return user

    def set_user_admin(self, user_id: int, is_admin: bool = True):
        """Установить/снять административные права"""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                user.is_admin = is_admin

    def is_user_admin(self, user_id: int) -> bool:
        """Проверить является ли пользователь админом"""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            return user.is_admin if user else False

    def update_user_state(self, user_id: int, state: str):
        """Обновить состояние пользователя"""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                user.current_state = state
                logger.info(f"Обновлено состояние пользователя {user_id}: {state}")

    def get_user_state(self, user_id: int) -> str:
        """Получить текущее состояние пользователя"""
        with self.get_session() as session:
            user = session.query(User).filter(User.user_id == user_id).first()
            return user.current_state if user else 'idle'

    # Методы для работы с балансом
    def get_user_balance(self, user_id: int) -> float:
        """Получить баланс пользователя"""
        with self.get_session() as session:
            balance = session.query(Balance).filter(Balance.user_id == user_id).first()
            return balance.amount if balance else 0.0

    def update_balance(self, user_id: int, amount: float) -> bool:
        """Обновить баланс пользователя (может быть отрицательным для списания)"""
        try:
            with self.get_session() as session:
                balance = session.query(Balance).filter(Balance.user_id == user_id).first()
                if balance:
                    new_amount = balance.amount + amount
                    if new_amount >= 0 or amount > 0:  # Разрешаем списание если есть средства или пополнение
                        balance.amount = new_amount
                        balance.last_updated = datetime.utcnow()
                        logger.info(f"Обновлен баланс пользователя {user_id}: {amount}, новый баланс: {new_amount}")
                        return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Ошибка обновления баланса: {e}")
            return False

    def check_balance(self, user_id: int, required_amount: float) -> bool:
        """Проверить достаточность средств"""
        current_balance = self.get_user_balance(user_id)
        return current_balance >= required_amount

    # Методы для работы с публикациями
    def create_publication(self, user_id: int, pub_type: str, text: str,
                           cost: float, **kwargs) -> int:
        """Создать новую публикацию"""
        with self.get_session() as session:
            publication = Publication(
                user_id=user_id,
                type=pub_type,
                text=text,
                cost=cost,
                firm_type=kwargs.get('firm_type'),
                firm_name=kwargs.get('firm_name'),
                created_at=datetime.utcnow()
            )
            session.add(publication)
            session.flush()
            logger.info(f"Создана публикация {publication.id} для пользователя {user_id}")
            return publication.id

    def update_publication_status(self, publication_id: int, status: str,
                                  message_id: int = None):
        """Обновить статус публикации"""
        with self.get_session() as session:
            publication = session.query(Publication).filter(
                Publication.id == publication_id
            ).first()
            if publication:
                publication.status = status
                if message_id:
                    publication.message_id = message_id
                if status == 'published':
                    publication.published_at = datetime.utcnow()
                logger.info(f"Обновлен статус публикации {publication_id}: {status}")

    # Методы для работы с платежами
    def create_payment(self, user_id: int, amount: float,
                       payment_method: str = None) -> int:
        """Создать новый платеж"""
        with self.get_session() as session:
            payment = Payment(
                user_id=user_id,
                amount=amount,
                payment_method=payment_method,
                created_at=datetime.utcnow()
            )
            session.add(payment)
            session.flush()
            logger.info(f"Создан платеж {payment.id} для пользователя {user_id} на сумму {amount}")
            return payment.id

    def complete_payment(self, payment_id: int, transaction_id: str = None) -> bool:
        """Завершить платеж"""
        try:
            with self.get_session() as session:
                payment = session.query(Payment).filter(Payment.id == payment_id).first()
                if payment and payment.status == 'pending':
                    payment.status = 'completed'
                    payment.transaction_id = transaction_id
                    payment.completed_at = datetime.utcnow()

                    # Обновляем баланс пользователя
                    self.update_balance(payment.user_id, payment.amount)
                    logger.info(f"Платеж {payment_id} завершен успешно")
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Ошибка завершения платежа: {e}")
            return False

    # Методы для работы со стоп-словами
    def add_stop_words(self, words: List[str], added_by: int):
        """Добавить стоп-слова"""
        with self.get_session() as session:
            for word in words:
                word = word.strip().lower()
                if not session.query(StopWord).filter(StopWord.word == word).first():
                    stop_word = StopWord(
                        word=word,
                        added_by=added_by,
                        created_at=datetime.utcnow()
                    )
                    session.add(stop_word)
            logger.info(f"Добавлено {len(words)} стоп-слов пользователем {added_by}")

    def get_all_stop_words(self) -> List[str]:
        """Получить все стоп-слова"""
        with self.get_session() as session:
            return [sw.word for sw in session.query(StopWord).all()]

    def clear_stop_words(self):
        """Очистить все стоп-слова"""
        with self.get_session() as session:
            deleted_count = session.query(StopWord).count()
            session.query(StopWord).delete()
            logger.info(f"Удалено {deleted_count} стоп-слов")

    def check_text_for_stop_words(self, text: str) -> List[str]:
        """Проверить текст на наличие стоп-слов"""
        stop_words = self.get_all_stop_words()
        text_lower = text.lower()
        found_words = []

        for stop_word in stop_words:
            if stop_word in text_lower:
                found_words.append(stop_word)

        return found_words

    # Методы для работы с сессиями
    def save_session_data(self, user_id: int, data: Dict[str, Any]):
        """Сохранить данные сессии"""
        with self.get_session() as session:
            user_session = session.query(UserSession).filter(
                UserSession.user_id == user_id
            ).first()

            if not user_session:
                user_session = UserSession(
                    user_id=user_id,
                    session_data=json.dumps(data, ensure_ascii=False),
                    last_updated=datetime.utcnow()
                )
                session.add(user_session)
            else:
                user_session.session_data = json.dumps(data, ensure_ascii=False)
                user_session.last_updated = datetime.utcnow()

            logger.debug(f"Сохранены данные сессии для пользователя {user_id}")

    def get_session_data(self, user_id: int) -> Dict[str, Any]:
        """Получить данные сессии"""
        with self.get_session() as session:
            user_session = session.query(UserSession).filter(
                UserSession.user_id == user_id
            ).first()

            if user_session and user_session.session_data:
                try:
                    return json.loads(user_session.session_data)
                except json.JSONDecodeError:
                    logger.error(f"Ошибка декодирования JSON сессии для пользователя {user_id}")
                    return {}
            return {}

    def clear_session_data(self, user_id: int):
        """Очистить данные сессии"""
        with self.get_session() as session:
            deleted_count = session.query(UserSession).filter(
                UserSession.user_id == user_id
            ).delete()
            logger.info(f"Очищены данные сессии для пользователя {user_id}")

    # Методы для работы с запланированными публикациями
    def create_scheduled_post(self, user_id: int, publication_id: int,
                              scheduled_time: datetime, frequency: str = 'once',
                              day_of_week: int = None, repetitions_left: int = 1) -> int:
        """Создать запланированную публикацию"""
        with self.get_session() as session:
            scheduled_post = ScheduledPost(
                user_id=user_id,
                publication_id=publication_id,
                scheduled_time=scheduled_time,
                frequency=frequency,
                day_of_week=day_of_week,
                repetitions_left=repetitions_left,
                created_at=datetime.utcnow()
            )
            session.add(scheduled_post)
            session.flush()
            logger.info(f"Создана запланированная публикация {scheduled_post.id}")
            return scheduled_post.id

    def get_scheduled_posts(self, user_id: int = None) -> List[ScheduledPost]:
        """Получить запланированные публикации"""
        with self.get_session() as session:
            query = session.query(ScheduledPost).filter(ScheduledPost.is_active == True)
            if user_id:
                query = query.filter(ScheduledPost.user_id == user_id)
            return query.all()

    def update_scheduled_post_repetitions(self, scheduled_post_id: int, repetitions_left: int):
        """Обновить количество оставшихся повторений"""
        with self.get_session() as session:
            scheduled_post = session.query(ScheduledPost).filter(
                ScheduledPost.id == scheduled_post_id
            ).first()
            if scheduled_post:
                scheduled_post.repetitions_left = repetitions_left
                if repetitions_left <= 0:
                    scheduled_post.is_active = False

    def deactivate_scheduled_post(self, scheduled_post_id: int):
        """Деактивировать запланированную публикацию"""
        with self.get_session() as session:
            scheduled_post = session.query(ScheduledPost).filter(
                ScheduledPost.id == scheduled_post_id
            ).first()
            if scheduled_post:
                scheduled_post.is_active = False
                logger.info(f"Деактивирована запланированная публикация {scheduled_post_id}")

    # Вспомогательные методы
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        with self.get_session() as session:
            return session.query(User).filter(User.user_id == user_id).first()

    def get_user_publications(self, user_id: int, limit: int = 10) -> List[Publication]:
        """Получить публикации пользователя"""
        with self.get_session() as session:
            return session.query(Publication).filter(
                Publication.user_id == user_id
            ).order_by(Publication.created_at.desc()).limit(limit).all()

    def get_user_payments(self, user_id: int, limit: int = 10) -> List[Payment]:
        """Получить платежи пользователя"""
        with self.get_session() as session:
            return session.query(Payment).filter(
                Payment.user_id == user_id
            ).order_by(Payment.created_at.desc()).limit(limit).all()

    # Статистические методы
    def get_total_users_count(self) -> int:
        """Получить общее количество пользователей"""
        with self.get_session() as session:
            return session.query(User).count()

    def get_total_publications_count(self) -> int:
        """Получить общее количество публикаций"""
        with self.get_session() as session:
            return session.query(Publication).count()

    def get_total_payments_sum(self) -> float:
        """Получить общую сумму платежей"""
        with self.get_session() as session:
            result = session.query(Payment.amount).filter(
                Payment.status == 'completed'
            ).all()
            return sum(payment.amount for payment in result) if result else 0.0