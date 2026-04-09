from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from db.models import Booking, BookingStatus, Class, Payment, PaymentStatus, Subscription, SubscriptionType, User
from db.queries import create_class, get_all_active_users
import logging

router = Router()
logger = logging.getLogger(__name__)

def is_admin(user_id):
    return user_id in settings.ADMIN_IDS

async def check_admin(event):
    if not is_admin(event.from_user.id):
        if isinstance(event, Message):
            await event.answer("⛔ Нет доступа")
        else:
            await event.answer("⛔ Нет доступа", show_alert=True)
        return False
    return True
