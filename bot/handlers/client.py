"""
Клиентские хэндлеры — /start, расписание, запись, мои занятия, абонемент.
"""

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Booking, BookingStatus, Class, Subscription, User
from db.queries import (
    cancel_booking,
    create_booking,
    decrement_subscription,
    get_active_subscription,
    get_booking,
    get_class_by_id,
    get_upcoming_classes,
    get_user_upcoming_bookings,
    SUBSCRIPTION_CLASSES,
)

router = Router()

DAYS_RU = {
    "Monday":    "Понедельник",
    "Tuesday":   "Вторник",
    "Wednesday": "Среда",
    "Thursday":  "Четверг",
    "Friday":    "Пятница",
    "Saturday":  "Суббота",
    "Sunday":    "Воскресенье",
}

DAYS_SHORT = {
    "Monday": "Пн", "Tuesday": "Вт", "Wednesday": "Ср",
    "Thursday": "Чт", "Friday": "Пт", "Saturday": "Сб", "Sunday": "Вс",
}


# ─────────────────────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, **kwargs):
    name = db_user.full_name.split()[0]
    text = (
        f"🧘 Привет, <b>{name}</b>!\n\n"
        f"Я помогу тебе:\n"
        f"📅 Посмотреть расписание занятий\n"
        f"✏️ Записаться и отменить запись\n"
        f"💳 Оплатить абонемент через Payme\n"
        f"📊 Следить за своим абонементом\n\n"
        f"Выбери что тебя интересует 👇"
    )
    await message.answer(text, reply_markup=_main_menu_kb())


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery, db_user: User, **kwargs):
    name = db_user.full_name.split()[0]
    await call.message.edit_text(
        f"🏠 Главное меню\n\nЧто хочешь сделать, <b>{name}</b>?",
        reply_markup=_main_menu_kb(),
    )
    await call.answer()


def _main_menu_kb():
    from aiogram.types import WebAppInfo
    b = InlineKeyboardBuilder()
    b.button(text="🌐 Открыть приложение", web_app=WebAppInfo(url="https://pilates.fapass.xyz/miniapp/"))
    b.button(text="📅 Расписание",        callback_data="schedule:0")
    b.button(text="🗓 Мои записи",        callback_data="my_bookings")
    b.button(text="💳 Абонемент",         callback_data="my_sub")
    b.button(text="📞 Контакты",          callback_data="contacts")
    b.adjust(1)
    return b.as_markup()


# ─────────────────────────────────────────────────────────────
# РАСПИСАНИЕ — красивое, с навигацией по дням
# ─────────────────────────────────────────────────────────────

@router.message(Command("schedule"))
@router.callback_query(F.data.startswith("schedule:"))
async def show_schedule(event, session: AsyncSession, db_user: User, **kwargs):
    # Определяем смещение дня
    if isinstance(event, CallbackQuery):
        day_offset = int(event.data.split(":")[1])
    else:
        day_offset = 0

    classes = await get_upcoming_classes(session, days=14)

    if not classes:
        text = "😔 На ближайшие 2 недели занятий нет.\n\nСледи за обновлениями!"
        b = InlineKeyboardBuilder()
        b.button(text="← Меню", callback_data="menu")
        b.adjust(1)
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=b.as_markup())
            await event.answer()
        else:
            await event.answer(text, reply_markup=b.as_markup())
        return

    # Группируем по дням
    days: dict[str, list[Class]] = {}
    for cls in classes:
        day_key = cls.starts_at.strftime("%Y-%m-%d")
        days.setdefault(day_key, []).append(cls)

    day_keys = sorted(days.keys())
    total_days = len(day_keys)

    # Ограничиваем offset
    day_offset = max(0, min(day_offset, total_days - 1))
    current_day_key = day_keys[day_offset]
    current_classes = days[current_day_key]
    current_dt = datetime.strptime(current_day_key, "%Y-%m-%d")

    day_name = DAYS_RU.get(current_dt.strftime("%A"), current_dt.strftime("%A"))
    day_str  = current_dt.strftime("%d.%m")
    is_today = current_dt.date() == datetime.now().date()
    today_label = " (сегодня)" if is_today else ""

    # Считаем записи клиента
    client_bookings = await get_user_upcoming_bookings(session, db_user.id)
    booked_class_ids = {b.class_id for b in client_bookings}

    # Строим текст расписания
    lines = [f"📅 <b>{day_name}, {day_str}{today_label}</b>\n"]

    for cls in sorted(current_classes, key=lambda c: c.starts_at):
        confirmed = [b for b in cls.bookings if b.status == BookingStatus.CONFIRMED]
        free = cls.max_spots - len(confirmed)

        if free > 2:
            spots_icon = "🟢"
            spots_text = f"{free} мест"
        elif free > 0:
            spots_icon = "🟡"
            spots_text = f"{free} мест"
        else:
            spots_icon = "🔴"
            spots_text = "нет мест"

        is_booked = cls.id in booked_class_ids
        booked_mark = " ✅ <i>ты записана</i>" if is_booked else ""

        lines.append(
            f"{spots_icon} <b>{cls.starts_at.strftime('%H:%M')}</b> — {cls.title}\n"
            f"   👤 {cls.trainer}  ·  {spots_text}{booked_mark}"
        )

    text = "\n\n".join(lines)

    # Клавиатура навигации
    b = InlineKeyboardBuilder()

    # Кнопки переключения дней
    nav_row = []
    if day_offset > 0:
        prev_dt  = datetime.strptime(day_keys[day_offset - 1], "%Y-%m-%d")
        prev_day = DAYS_SHORT.get(prev_dt.strftime("%A"), "")
        b.button(text=f"◀ {prev_day} {prev_dt.strftime('%d.%m')}", callback_data=f"schedule:{day_offset - 1}")
    if day_offset < total_days - 1:
        next_dt  = datetime.strptime(day_keys[day_offset + 1], "%Y-%m-%d")
        next_day = DAYS_SHORT.get(next_dt.strftime("%A"), "")
        b.button(text=f"{next_day} {next_dt.strftime('%d.%m')} ▶", callback_data=f"schedule:{day_offset + 1}")

    b.adjust(2)

    # Кнопки записи на занятия этого дня
    for cls in sorted(current_classes, key=lambda c: c.starts_at):
        confirmed = [bk for bk in cls.bookings if bk.status == BookingStatus.CONFIRMED]
        free = cls.max_spots - len(confirmed)
        is_booked = cls.id in booked_class_ids

        if is_booked:
            b.button(text=f"✅ Записана {cls.starts_at.strftime('%H:%M')} — отменить", callback_data=f"cancel_from_schedule:{cls.id}")
        elif free > 0:
            b.button(text=f"🟢 Записаться {cls.starts_at.strftime('%H:%M')}", callback_data=f"book_{cls.id}")
        else:
            b.button(text=f"🔴 {cls.starts_at.strftime('%H:%M')} — мест нет", callback_data="full")
        b.adjust(1)

    b.button(text="← Меню", callback_data="menu")
    b.adjust(1)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=b.as_markup())
        await event.answer()
    else:
        await event.answer(text, reply_markup=b.as_markup())


# ─────────────────────────────────────────────────────────────
# ЗАПИСЬ
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "book")
async def show_booking_list(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    classes = await get_upcoming_classes(session, days=7)
    available = [c for c in classes if c.free_spots > 0]

    if not available:
        b = InlineKeyboardBuilder()
        b.button(text="← Меню", callback_data="menu")
        b.adjust(1)
        await call.message.edit_text(
            "😔 Свободных мест нет. Загляни позже или следи за расписанием!",
            reply_markup=b.as_markup(),
        )
        await call.answer()
        return

    b = InlineKeyboardBuilder()
    current_day = None
    for cls in available:
        day_label = cls.starts_at.strftime("%d.%m")
        day_name  = DAYS_SHORT.get(cls.starts_at.strftime("%A"), "")
        spots     = cls.free_spots
        spots_icon = "🟢" if spots > 2 else "🟡"
        b.button(
            text=f"{spots_icon} {day_name} {day_label} {cls.starts_at.strftime('%H:%M')} — {cls.title[:20]}",
            callback_data=f"book_{cls.id}",
        )
    b.button(text="← Меню", callback_data="menu")
    b.adjust(1)

    await call.message.edit_text("✏️ <b>Выбери занятие:</b>", reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data == "full")
async def spot_full(call: CallbackQuery, **kwargs):
    await call.answer("😔 Мест нет. Попробуй другое занятие!", show_alert=True)


@router.callback_query(F.data.startswith("book_"))
async def confirm_booking_prompt(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    class_id = int(call.data.split("_")[1])
    cls = await get_class_by_id(session, class_id)
    if not cls:
        await call.answer("Занятие не найдено", show_alert=True)
        return

    existing = await get_booking(session, db_user.id, class_id)
    if existing and existing.status == BookingStatus.CONFIRMED:
        await call.answer("✅ Ты уже записана на это занятие!", show_alert=True)
        return

    sub = await get_active_subscription(session, db_user.id)
    if sub:
        sub_info = f"✅ Абонемент: <b>{sub.classes_left} занятий</b> осталось"
    else:
        sub_info = (
            "⚠️ <b>Активного абонемента нет.</b>\n"
            "Оплати занятие через кнопку 💳 Оплатить"
        )

    spots = cls.free_spots
    spots_icon = "🟢" if spots > 2 else "🟡" if spots > 0 else "🔴"

    b = InlineKeyboardBuilder()
    if sub:
        b.button(text="✅ Записаться", callback_data=f"confirm_book_{class_id}")
    else:
        b.button(text="💳 Купить абонемент", callback_data="pay")
    b.button(text="← Расписание", callback_data="schedule:0")
    b.adjust(1)

    await call.message.edit_text(
        f"📌 <b>Подтверди запись:</b>\n\n"
        f"🧘 {cls.title}\n"
        f"📅 {cls.starts_at.strftime('%d.%m.%Y в %H:%M')}\n"
        f"👤 Тренер: {cls.trainer}\n"
        f"{spots_icon} Мест: {spots}/{cls.max_spots}\n\n"
        f"{sub_info}",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("confirm_book_"))
async def do_booking(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    class_id = int(call.data.split("_")[2])
    cls = await get_class_by_id(session, class_id)
    if not cls or cls.free_spots <= 0:
        await call.answer("😔 Мест уже нет!", show_alert=True)
        return

    await create_booking(session, db_user.id, class_id)
    await decrement_subscription(session, db_user.id)

    b = InlineKeyboardBuilder()
    b.button(text="🗓 Мои записи", callback_data="my_bookings")
    b.button(text="← Меню", callback_data="menu")
    b.adjust(1)

    await call.message.edit_text(
        f"🎉 <b>Ты записана!</b>\n\n"
        f"🧘 {cls.title}\n"
        f"📅 {cls.starts_at.strftime('%d.%m.%Y в %H:%M')}\n"
        f"👤 Тренер: {cls.trainer}\n\n"
        f"⏰ Напомню за 24 часа и за 2 часа до занятия.",
        reply_markup=b.as_markup(),
    )
    await call.answer("✅ Запись подтверждена!")


@router.callback_query(F.data.startswith("cancel_from_schedule:"))
async def cancel_from_schedule(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    class_id = int(call.data.split(":")[1])
    existing = await get_booking(session, db_user.id, class_id)
    if not existing:
        await call.answer("Запись не найдена", show_alert=True)
        return
    cls = await get_class_by_id(session, class_id)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, отменить", callback_data=f"confirm_cancel_{existing.id}")
    b.button(text="← Назад", callback_data="schedule:0")
    b.adjust(1)
    await call.message.edit_text(
        f"Отменить запись?\n\n"
        f"🧘 {cls.title}\n"
        f"📅 {cls.starts_at.strftime('%d.%m.%Y в %H:%M')}\n"
        f"👤 {cls.trainer}",
        reply_markup=b.as_markup(),
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────
# МОИ ЗАПИСИ
# ─────────────────────────────────────────────────────────────

@router.message(Command("mybookings"))
@router.callback_query(F.data == "my_bookings")
async def my_bookings(event, session: AsyncSession, db_user: User, **kwargs):
    bookings = await get_user_upcoming_bookings(session, db_user.id)

    b = InlineKeyboardBuilder()
    if not bookings:
        text = (
            "🗓 <b>Предстоящих занятий нет.</b>\n\n"
            "Запишись через расписание 📅"
        )
        b.button(text="📅 Расписание", callback_data="schedule:0")
        b.button(text="🏠 В меню",    callback_data="menu")
        b.adjust(1)
    else:
        lines = ["🗓 <b>Твои ближайшие занятия:</b>\n"]
        for bk in bookings:
            day_name = DAYS_RU.get(bk.cls.starts_at.strftime("%A"), "")
            lines.append(
                f"📌 <b>{bk.cls.starts_at.strftime('%d.%m')} {day_name}</b>\n"
                f"   🕐 {bk.cls.starts_at.strftime('%H:%M')} — {bk.cls.title}\n"
                f"   👤 {bk.cls.trainer}"
            )
        text = "\n\n".join(lines)

        for bk in bookings:
            b.button(
                text=f"❌ Отменить {bk.cls.starts_at.strftime('%d.%m %H:%M')} {bk.cls.title[:15]}",
                callback_data=f"cancel_booking_{bk.id}",
            )
        b.button(text="← Меню", callback_data="menu")
        b.adjust(1)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=b.as_markup())
        await event.answer()
    else:
        await event.answer(text, reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking_cb(call: CallbackQuery, session: AsyncSession, **kwargs):
    booking_id = int(call.data.split("_")[2])
    from db.models import Booking as BookingModel
    bk = await session.get(BookingModel, booking_id)
    if not bk:
        await call.answer("Запись не найдена", show_alert=True)
        return
    cls = await get_class_by_id(session, bk.class_id)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, отменить", callback_data=f"confirm_cancel_{booking_id}")
    b.button(text="← Назад", callback_data="my_bookings")
    b.adjust(1)
    await call.message.edit_text(
        f"Отменить запись?\n\n"
        f"🧘 {cls.title}\n"
        f"📅 {cls.starts_at.strftime('%d.%m.%Y в %H:%M')}\n"
        f"👤 {cls.trainer}",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("confirm_cancel_"))
async def confirm_cancel_cb(call: CallbackQuery, session: AsyncSession, **kwargs):
    booking_id = int(call.data.split("_")[2])
    await cancel_booking(session, booking_id)

    b = InlineKeyboardBuilder()
    b.button(text="📅 Расписание", callback_data="schedule:0")
    b.button(text="← Меню", callback_data="menu")
    b.adjust(1)

    await call.message.edit_text(
        "✅ <b>Запись отменена.</b>\n\nМесто освобождено для других. До встречи! 💛",
        reply_markup=b.as_markup(),
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────
# МОЙ АБОНЕМЕНТ
# ─────────────────────────────────────────────────────────────

@router.message(Command("mysub"))
@router.callback_query(F.data == "my_sub")
async def my_subscription(event, session: AsyncSession, db_user: User, **kwargs):
    sub = await get_active_subscription(session, db_user.id)

    b = InlineKeyboardBuilder()
    if not sub:
        text = (
            "💳 <b>Активного абонемента нет.</b>\n\n"
            "Купи абонемент прямо здесь — быстро и безопасно через Payme 👇"
        )
        b.button(text="💳 Купить абонемент", callback_data="pay")
    else:
        expires = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "без ограничений"
        total = SUBSCRIPTION_CLASSES.get(sub.sub_type, sub.classes_left)
        used = total - sub.classes_left
        bar = "🟩" * sub.classes_left + "⬜" * used

        text = (
            f"📊 <b>Твой абонемент</b>\n\n"
            f"{bar}\n"
            f"✅ Осталось занятий: <b>{sub.classes_left}</b>\n"
            f"📅 Действует до: <b>{expires}</b>\n\n"
            f"Записывайся на занятия пока есть места! 🧘"
        )
        b.button(text="📅 Расписание", callback_data="schedule:0")
        b.button(text="💳 Купить ещё", callback_data="pay")

    b.button(text="← Меню", callback_data="menu")
    b.adjust(1)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=b.as_markup())
        await event.answer()
    else:
        await event.answer(text, reply_markup=b.as_markup())


# ─────────────────────────────────────────────────────────────
# КОНТАКТЫ
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "contacts")
async def contacts(call: CallbackQuery, **kwargs):
    b = InlineKeyboardBuilder()
    b.button(text="← Меню", callback_data="menu")
    b.adjust(1)
    await call.message.edit_text(
        "📍 <b>Студия пилатеса</b>\n\n"
        "📍 Адрес: ул. Примерная, 10\n"
        "📞 Телефон: +7 (999) 123-45-67\n"
        "💬 Instagram: @pilates_studio\n\n"
        "🕐 Пн–Пт: 8:00–21:00\n"
        "🕐 Сб–Вс: 9:00–18:00",
        reply_markup=b.as_markup(),
    )
    await call.answer()
