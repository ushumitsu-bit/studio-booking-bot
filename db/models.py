"""
Модели базы данных.

Таблицы:
  users        — клиенты (Telegram-пользователи)
  classes      — занятия в расписании
  bookings     — записи клиентов на занятия
  subscriptions— абонементы
  payments     — история платежей через ЮKassa
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum,
    ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────── Enums ───────────────────────────────

class BookingStatus(str, PyEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    MISSED    = "missed"      # пропустил без отмены
    ATTENDED  = "attended"


class PaymentStatus(str, PyEnum):
    PENDING   = "pending"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"


class SubscriptionType(str, PyEnum):
    SINGLE   = "single"      # 1 занятие
    PACK_4   = "pack_4"      # 4 занятия
    PACK_8   = "pack_8"      # 8 занятий


# ─────────────────────────── Таблицы ─────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(BigInteger, primary_key=True)   # Telegram user_id
    username      = Column(String(64), nullable=True)
    full_name     = Column(String(128), nullable=False)
    phone         = Column(String(20), nullable=True)
    is_admin      = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    bookings      = relationship("Booking", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    payments      = relationship("Payment", back_populates="user")


class Class(Base):
    __tablename__ = "classes"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    title       = Column(String(128), nullable=False)       # «Пилатес для начинающих»
    trainer     = Column(String(64), nullable=False)
    starts_at   = Column(DateTime, nullable=False)          # дата+время начала
    duration_min= Column(Integer, default=60)               # продолжительность, мин
    max_spots   = Column(Integer, default=8)
    is_cancelled= Column(Boolean, default=False)

    bookings    = relationship("Booking", back_populates="cls")

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
    reminder_sent  = Column(Boolean, default=False)   # 24ч напоминание
    reminder2_sent = Column(Boolean, default=False)   # 2ч напоминание
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    cls  = relationship("Class", back_populates="bookings")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    sub_type    = Column(Enum(SubscriptionType), nullable=False)
    classes_left= Column(Integer, nullable=False)        # остаток занятий
    expires_at  = Column(DateTime, nullable=True)        # срок действия
    expiry_warned= Column(Boolean, default=False)        # уведомление отправлено
    created_at  = Column(DateTime, default=datetime.utcnow)

    user     = relationship("User", back_populates="subscriptions")
    payment  = relationship("Payment", back_populates="subscription", uselist=False)


class Payment(Base):
    __tablename__ = "payments"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    yukassa_id      = Column(String(64), unique=True, nullable=True)  # ID платежа в ЮKassa
    amount          = Column(Integer, nullable=False)                 # сумма в рублях
    status          = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    description     = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    paid_at         = Column(DateTime, nullable=True)

    user         = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payment")
