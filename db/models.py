"""
Модели базы данных.

Таблицы:
  users        — клиенты (Telegram-пользователи)
  classes      — занятия в расписании
  bookings     — записи клиентов на занятия
  subscriptions— абонементы
  payments     — история платежей через Payme
  waitlist     — лист ожидания (занятие заполнено)
  class_feedback — отзывы после занятия
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum,
    ForeignKey, Integer, SmallInteger, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────── Enums ───────────────────────────────

class BookingStatus(str, PyEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    MISSED    = "missed"
    ATTENDED  = "attended"


class PaymentStatus(str, PyEnum):
    PENDING   = "pending"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"


class SubscriptionType(str, PyEnum):
    SINGLE   = "single"
    PACK_4   = "pack_4"
    PACK_8   = "pack_8"
    PACK_12  = "pack_12"
    PACK_16  = "pack_16"
    TRIAL    = "trial"      # пробное занятие (1 раз, льготная цена)


class Gender(str, PyEnum):
    FEMALE = "female"
    MALE   = "male"


class FitnessLevel(str, PyEnum):
    BEGINNER     = "beginner"      # никогда не занимался
    BASIC        = "basic"         # до 6 месяцев
    INTERMEDIATE = "intermediate"  # 6 мес – 2 года
    ADVANCED     = "advanced"      # 2+ года


class ClassPreference(str, PyEnum):
    GROUP      = "group"
    INDIVIDUAL = "individual"
    BOTH       = "both"


class UserLanguage(str, PyEnum):
    RU = "ru"
    UZ = "uz"
    EN = "en"


# ─────────────────────────── Таблицы ─────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(BigInteger, primary_key=True)
    username      = Column(String(64), nullable=True)
    full_name     = Column(String(128), nullable=False)
    phone         = Column(String(20), nullable=True)
    is_admin      = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    # Onboarding / profile
    onboarding_done   = Column(Boolean, default=False)
    language          = Column(Enum(UserLanguage), default=UserLanguage.RU)
    gender            = Column(Enum(Gender), nullable=True)
    fitness_level     = Column(Enum(FitnessLevel), nullable=True)
    class_preference  = Column(Enum(ClassPreference), nullable=True)
    health_notes      = Column(Text, nullable=True)

    # Активность
    streak_count      = Column(Integer, default=0)
    last_attended_at  = Column(DateTime, nullable=True)

    bookings      = relationship("Booking", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    payments      = relationship("Payment", back_populates="user")
    waitlist      = relationship("Waitlist", back_populates="user")
    feedback      = relationship("ClassFeedback", back_populates="user")


class Class(Base):
    __tablename__ = "classes"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    title       = Column(String(128), nullable=False)
    trainer     = Column(String(64), nullable=False)
    starts_at   = Column(DateTime, nullable=False)
    duration_min= Column(Integer, default=60)
    max_spots   = Column(Integer, default=8)
    is_cancelled= Column(Boolean, default=False)
    location        = Column(String(128), default="Студия")
    payment_enabled = Column(Boolean, default=True)
    booking_enabled = Column(Boolean, default=True)
    zoom_link       = Column(String(256), nullable=True)   # для онлайн-формата

    bookings  = relationship("Booking", back_populates="cls")
    waitlist  = relationship("Waitlist", back_populates="cls")
    feedback  = relationship("ClassFeedback", back_populates="cls")

    @property
    def free_spots(self) -> int:
        confirmed = [b for b in self.bookings if b.status == BookingStatus.CONFIRMED]
        return self.max_spots - len(confirmed)


class Booking(Base):
    __tablename__ = "bookings"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    class_id   = Column(Integer, ForeignKey("classes.id"), nullable=False)
    status     = Column(Enum(BookingStatus), default=BookingStatus.CONFIRMED)
    reminder_sent  = Column(Boolean, default=False)
    reminder2_sent = Column(Boolean, default=False)
    feedback_sent  = Column(Boolean, default=False)   # запрос отзыва отправлен
    streak_updated = Column(Boolean, default=False)   # streak пользователя уже обновлён
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    cls  = relationship("Class", back_populates="bookings")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    sub_type    = Column(Enum(SubscriptionType), nullable=False)
    classes_left= Column(Integer, nullable=False)
    expires_at  = Column(DateTime, nullable=True)
    expiry_warned       = Column(Boolean, default=False)
    low_classes_warned  = Column(Boolean, default=False)

    # Заморозка
    is_frozen   = Column(Boolean, default=False)
    frozen_until= Column(DateTime, nullable=True)

    created_at  = Column(DateTime, default=datetime.utcnow)

    user     = relationship("User", back_populates="subscriptions")
    payment  = relationship("Payment", back_populates="subscription", uselist=False)


class Payment(Base):
    __tablename__ = "payments"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    payme_id        = Column(String(64), unique=True, nullable=True)
    amount          = Column(Integer, nullable=False)
    status          = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    description     = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    paid_at         = Column(DateTime, nullable=True)

    user         = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payment")


class Waitlist(Base):
    __tablename__ = "waitlist"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    class_id   = Column(Integer, ForeignKey("classes.id"), nullable=False)
    notified   = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="waitlist")
    cls  = relationship("Class", back_populates="waitlist")


class ClassFeedback(Base):
    __tablename__ = "class_feedback"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    class_id   = Column(Integer, ForeignKey("classes.id"), nullable=False)
    rating     = Column(SmallInteger, nullable=False)   # 1–5
    comment    = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="feedback")
    cls  = relationship("Class", back_populates="feedback")
