from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    current_state = Column(String(50), default='idle')
    registration_date = Column(DateTime, default=datetime.utcnow)

    # Связи
    balance = relationship("Balance", back_populates="user", uselist=False)
    publications = relationship("Publication", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    scheduled_posts = relationship("ScheduledPost", back_populates="user")

class Balance(Base):
    """Модель баланса пользователя"""
    __tablename__ = 'balance'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), unique=True)
    amount = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    user = relationship("User", back_populates="balance")

class Publication(Base):
    """Модель публикации"""
    __tablename__ = 'publications'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    type = Column(String(50), nullable=False)  # 'ad', 'job_search', 'job_offer'
    firm_type = Column(String(50), nullable=True)
    firm_name = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)  # Название вакансии
    worker_count = Column(String(100), nullable=True)  # Количество работников
    work_period = Column(String(255), nullable=True)  # Период работы
    work_conditions = Column(Text, nullable=True)  # Условия работы
    requirements = Column(Text, nullable=True)  # Требования
    salary = Column(String(255), nullable=True)  # Зарплата
    contacts = Column(String(500), nullable=True)  # Контакты
    text = Column(Text, nullable=False)
    status = Column(String(50), default='draft')  # 'draft', 'published', 'scheduled'
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    cost = Column(Float, nullable=False)
    message_id = Column(Integer, nullable=True)  # ID сообщения в группе

    # Связи
    user = relationship("User", back_populates="publications")

class Payment(Base):
    """Модель платежа"""
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    amount = Column(Float, nullable=False)
    status = Column(String(50), default='pending')  # 'pending', 'completed', 'failed'
    payment_method = Column(String(50), nullable=True)
    transaction_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Связи
    user = relationship("User", back_populates="payments")

class ScheduledPost(Base):
    """Модель отложенных публикаций"""
    __tablename__ = 'scheduled_posts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    publication_id = Column(Integer, ForeignKey('publications.id'))
    scheduled_time = Column(DateTime, nullable=False)
    frequency = Column(String(50), nullable=True)  # 'once', 'daily', 'weekly'
    day_of_week = Column(Integer, nullable=True)  # 0-6 для еженедельных
    repetitions_left = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    user = relationship("User", back_populates="scheduled_posts")
    publication = relationship("Publication")

class StopWord(Base):
    """Модель стоп-слов"""
    __tablename__ = 'stop_words'

    id = Column(Integer, primary_key=True)
    word = Column(String(255), nullable=False, unique=True)
    added_by = Column(Integer, ForeignKey('users.user_id'))
    created_at = Column(DateTime, default=datetime.utcnow)

class UserSession(Base):
    """Модель пользовательской сессии для хранения временных данных"""
    __tablename__ = 'user_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), unique=True)
    session_data = Column(Text)  # JSON данные сессии
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
