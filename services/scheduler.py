from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
from typing import Optional
import pytz
import os
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class PublicationScheduler:
    """Планировщик для автоматических публикаций"""

    def __init__(self, db_manager: DatabaseManager, bot, group_id: int):
        self.db = db_manager
        self.bot = bot
        self.group_id = group_id
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        logger.info("Планировщик публикаций запущен")

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

    async def schedule_single_post(self, user_id: int, text: str,
                                   scheduled_time: datetime, pub_type: str) -> str:
        """
        Запланировать одиночную публикацию

        Args:
            user_id: ID пользователя
            text: Текст публикации
            scheduled_time: Дата и время публикации
            pub_type: Тип публикации (advertisement, job_offer, job_search)

        Returns:
            str: ID задачи планировщика
        """
        try:
            # Убедимся, что время в UTC
            if scheduled_time.tzinfo is None:
                scheduled_time = scheduled_time.replace(tzinfo=pytz.UTC)

            job_id = f"single_{user_id}_{int(scheduled_time.timestamp())}"

            # Сохраняем публикацию в БД
            publication_id = self.db.create_publication(
                user_id=user_id,
                pub_type=pub_type,
                text=text,
                cost=0,  # Стоимость уже списана
                status='scheduled'
            )

            # Добавляем задачу в планировщик
            self.scheduler.add_job(
                self._publish_post,
                trigger=DateTrigger(run_date=scheduled_time),
                args=[user_id, text, pub_type, publication_id],
                id=job_id,
                replace_existing=True
            )

            logger.info(f"Запланирована публикация на {scheduled_time} для пользователя {user_id}")
            return job_id
        except Exception as e:
            logger.error(f"Ошибка планирования публикации: {e}")
            raise

    async def schedule_recurring_post(self, user_id: int, text: str,
                                      frequency: str, time_str: str,
                                      day_of_week: Optional[int] = None,
                                      repetitions: int = 1, pub_type: str = "advertisement") -> str:
        """
        Запланировать повторяющуюся публикацию

        Args:
            user_id: ID пользователя
            text: Текст публикации
            frequency: Частота публикации ("daily" или "weekly")
            time_str: Время публикации в формате "ЧЧ:ММ"
            day_of_week: День недели (0-6, где 0 - понедельник) для еженедельных публикаций
            repetitions: Количество повторений
            pub_type: Тип публикации

        Returns:
            str: ID задачи планировщика
        """
        try:
            job_id = f"recurring_{user_id}_{int(datetime.now().timestamp())}"

            # Парсим время
            hour, minute = map(int, time_str.split(':'))

            # Определяем триггер в зависимости от частоты
            if frequency == "daily":
                trigger = CronTrigger(hour=hour, minute=minute)
                # Для ежедневной публикации рассчитываем, сколько дней публиковать
                end_date = datetime.now() + timedelta(days=repetitions)
            elif frequency == "weekly" and day_of_week is not None:
                trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
                # Для еженедельной публикации рассчитываем дату окончания
                # Например, для 4 повторений публикуем 4 недели
                end_date = datetime.now() + timedelta(weeks=repetitions)
            else:
                raise ValueError(f"Неподдерживаемая частота: {frequency}")

            # Сохраняем информацию о запланированных постах в БД
            for i in range(repetitions):
                # Рассчитываем примерную дату публикации для записи в БД
                if frequency == "daily":
                    planned_date = datetime.now() + timedelta(days=i)
                else:  # weekly
                    planned_date = datetime.now() + timedelta(weeks=i)
                planned_date = planned_date.replace(hour=hour, minute=minute)

                # Создаем запись в БД для каждого поста
                self.db.create_publication(
                    user_id=user_id,
                    pub_type=pub_type,
                    text=text,
                    cost=0,  # Стоимость уже списана
                    status='scheduled'
                )

            # Добавляем задачу в планировщик
            self.scheduler.add_job(
                self._publish_recurring_post,
                trigger=trigger,
                args=[user_id, text, pub_type, repetitions, job_id],
                id=job_id,
                end_date=end_date,
                replace_existing=True
            )

            logger.info(f"Запланирована повторяющаяся публикация ({frequency}) для пользователя {user_id}")
            return job_id
        except Exception as e:
            logger.error(f"Ошибка планирования повторяющейся публикации: {e}")
            raise

    async def _publish_post(self, user_id: int, text: str, pub_type: str, publication_id: int = None):
        """
        Опубликовать пост в группе

        Args:
            user_id: ID пользователя
            text: Текст публикации
            pub_type: Тип публикации
            publication_id: ID публикации в БД (если есть)
        """
        try:
            # Определяем изображение в зависимости от типа публикации
            image_path = self._get_image_path_for_publication(pub_type)

            # Проверяем наличие изображения
            if os.path.exists(image_path):
                # Отправляем сообщение с изображением в группу
                with open(image_path, 'rb') as photo:
                    message = await self.bot.send_photo(
                        chat_id=self.group_id,
                        photo=photo,
                        caption=text,
                        parse_mode='HTML'
                    )
            else:
                # Если изображение не найдено, отправляем только текст
                logger.warning(f"Изображение {image_path} не найдено. Отправляем только текст")
                message = await self.bot.send_message(
                    chat_id=self.group_id,
                    text=text,
                    parse_mode='HTML'
                )

            # Если не передан ID публикации, создаем новую запись
            if publication_id is None:
                publication_id = self.db.create_publication(
                    user_id=user_id,
                    pub_type=pub_type,
                    text=text,
                    cost=0  # Уже оплачено
                )

            # Обновляем статус публикации
            self.db.update_publication_status(
                publication_id=publication_id,
                status='published',
                message_id=message.message_id
            )

            logger.info(f"Опубликован пост пользователя {user_id} в группе {self.group_id}")
            # Уведомляем пользователя об успешной публикации
            await self._notify_user_published(user_id, pub_type, datetime.now())
        except Exception as e:
            logger.error(f"Ошибка публикации поста пользователя {user_id}: {e}")
            await self._notify_user_error(user_id, str(e))

    async def _publish_recurring_post(self, user_id: int, text: str, pub_type: str,
                                      repetitions_left: int, job_id: str):
        """
        Опубликовать повторяющийся пост

        Args:
            user_id: ID пользователя
            text: Текст публикации
            pub_type: Тип публикации
            repetitions_left: Количество оставшихся повторений
            job_id: ID задачи
        """
        try:
            # Публикуем пост
            await self._publish_post(user_id, text, pub_type)

            # Уменьшаем счетчик в БД если есть такая необходимость
            # Это не обязательно, так как мы используем end_date для ограничения

            # Для отладки
            logger.info(f"Опубликован повторяющийся пост, задача {job_id}")
        except Exception as e:
            logger.error(f"Ошибка публикации повторяющегося поста: {e}")
            # Не уведомляем пользователя, так как это уже делается в _publish_post

    async def _notify_user_published(self, user_id: int, pub_type: str, published_time: datetime):
        """
        Уведомить пользователя об успешной публикации

        Args:
            user_id: ID пользователя
            pub_type: Тип публикации
            published_time: Время публикации
        """
        try:
            pub_type_text = "реклама" if pub_type == "advertisement" else "объявление"
            time_str = published_time.strftime("%d.%m.%Y в %H:%M")
            text = f"✅ Ваша {pub_type_text} опубликована {time_str}"
            await self.bot.send_message(
                chat_id=user_id,
                text=text
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя {user_id}: {e}")

    async def _notify_user_error(self, user_id: int, error_message: str):
        """
        Уведомить пользователя об ошибке публикации

        Args:
            user_id: ID пользователя
            error_message: Текст ошибки
        """
        try:
            text = f"❌ Ошибка при публикации: {error_message}"
            await self.bot.send_message(
                chat_id=user_id,
                text=text
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления об ошибке пользователя {user_id}: {e}")

    def cancel_job(self, job_id: str) -> bool:
        """
        Отменить запланированную задачу

        Args:
            job_id: ID задачи

        Returns:
            bool: Успешность отмены
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Отменена задача {job_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка отмены задачи {job_id}: {e}")
            return False

    def get_scheduled_jobs(self, user_id: int) -> list:
        """
        Получить список запланированных задач для пользователя

        Args:
            user_id: ID пользователя

        Returns:
            list: Список задач
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            # Проверяем, что это задача пользователя
            if job.id.startswith(f"single_{user_id}_") or job.id.startswith(f"recurring_{user_id}_"):
                jobs.append({
                    'id': job.id,
                    'next_run': job.next_run_time,
                    'trigger': str(job.trigger)
                })
        return jobs

    def shutdown(self):
        """Остановить планировщик"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик публикаций остановлен")
