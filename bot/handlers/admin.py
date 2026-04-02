"""
Админ-панель прямо в Telegram.

Что умеет:
  /admin              — главное меню со статистикой
  📅 Добавить занятие — быстрый выбор из шаблонов или своё название
  👥 Клиенты          — список, карточка, начислить занятие, пнуть, заблокировать
  💰 Платежи          — последние 15 оплат + общая сумма за месяц
  📣 Рассылка         — текст → предпросмотр → отправить всем
  📊 Статистика       — сводка по студии
"""

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
from db.engine import AsyncSessionFactory
from db.models import (
    Booking, BookingStatus, Class, Payment,
    PaymentStatus, Subscription, SubscriptionType, User,
)
from db.queries import create_class, get_all_active_users

router = Router()

# ─── Проверка прав ────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS

async def check_admin(event) -> bool:
    if not is_admin(event.from_user.id):
        if isinstance(event, Message):
            await event.answer("⛔ Нет доступа")
        else:
            await event.answer("⛔ Нет доступа", show_alert=True)
        return False
    return True

# ─── FSM ─────────────────────────────────────────────────────────

class AddClassFSM(StatesGroup):
    title     = State()
    trainer   = State()
    date_time = State()
    max_spots = State()

class BroadcastFSM(StatesGroup):
    text    = State()
    confirm = State()

# ─── Шаблоны ─────────────────────────────────────────────────────

CLASS_TEMPLATES = [
    "Пилатес для начинающих",
    "Пилатес на реформере",
    "Стретчинг + пилатес",
    "Пилатес продвинутый",
    "Индивидуальное занятие",
]

TRAINER_LIST = [
    "Юлия Николаева",
    "Анна Громова",
]

PAGE_SIZE = 8

# ═══════════════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════════════════════════════

async def build_main_text(session: AsyncSession) -> str:
    today_start = datetime.now().replace(hour=0, minute=0, second=0)
    today_end   = today_start + timedelta(days=1)

    total_users = await session.scalar(
        select(func.count(User.id)).where(User.is_active == True)
    ) or 0
    today_classes = await session.scalar(
        select(func.count(Class.id)).where(
            Class.starts_at >= today_start,
            Class.starts_at < today_end,
            Class.is_cancelled == False,
        )
    ) or 0
    active_sub_ids = select(Subscription.user_id).where(Subscription.classes_left > 0)
    no_sub = await session.scalar(
        select(func.count(User.id)).where(
            User.is_active == True,
            User.id.not_in(active_sub_ids),
        )
    ) or 0
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    month_income = await session.scalar(
        select(func.sum(Payment.amount)).where(
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.paid_at >= month_start,
        )
    ) or 0

    return (
        f"🛠 <b>Панель администратора</b>\n\n"
        f"👥 Клиентов: <b>{total_users}</b>  ·  без абонемента: <b>{no_sub}</b>\n"
        f"📅 Занятий сегодня: <b>{today_classes}</b>\n"
        f"💰 Доход за месяц: <b>{month_income} ₽</b>"
    )

def main_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📅 Добавить занятие", callback_data="adm:addclass")
    b.button(text="📋 Расписание",        callback_data="adm:schedule")
    b.button(text="👥 Клиенты",           callback_data="adm:clients:0")
    b.button(text="💰 Платежи",           callback_data="adm:payments")
    b.button(text="📣 Рассылка",          callback_data="adm:broadcast")
    b.button(text="📊 Статистика",        callback_data="adm:stats")
    b.adjust(1, 2, 2, 1)
    return b.as_markup()

@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    if not await check_admin(message):
        return
    text = await build_main_text(session)
    await message.answer(text, reply_markup=main_menu_kb())

@router.callback_query(F.data == "adm:main")
async def cb_admin_main(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    text = await build_main_text(session)
    await call.message.edit_text(text, reply_markup=main_menu_kb())
    await call.answer()

# ═══════════════════════════════════════════════════════════════
# ДОБАВИТЬ ЗАНЯТИЕ
# ═══════════════════════════════════════════════════════════════

def templates_kb():
    b = InlineKeyboardBuilder()
    for t in CLASS_TEMPLATES:
        b.button(text=t, callback_data=f"adm:title:{t[:40]}")
    b.button(text="✏️ Своё название", callback_data="adm:title:custom")
    b.button(text="◀️ Назад",         callback_data="adm:main")
    b.adjust(1)
    return b.as_markup()

def trainers_kb():
    b = InlineKeyboardBuilder()
    for t in TRAINER_LIST:
        b.button(text=t, callback_data=f"adm:trainer:{t}")
    b.button(text="✏️ Другой тренер", callback_data="adm:trainer:custom")
    b.button(text="◀️ Назад",         callback_data="adm:addclass")
    b.adjust(1)
    return b.as_markup()

def spots_kb():
    b = InlineKeyboardBuilder()
    for n in [4, 6, 8, 10, 12]:
        b.button(text=str(n), callback_data=f"adm:spots:{n}")
    b.adjust(5)
    return b.as_markup()

@router.callback_query(F.data == "adm:addclass")
async def cb_addclass(call: CallbackQuery, state: FSMContext):
    if not await check_admin(call):
        return
    await state.clear()
    await state.set_state(AddClassFSM.title)
    await call.message.edit_text(
        "📅 <b>Добавить занятие — шаг 1/4</b>\n\nВыбери название или введи своё:",
        reply_markup=templates_kb(),
    )
    await call.answer()

# Шаг 1 — название
@router.callback_query(F.data.startswith("adm:title:"), AddClassFSM.title)
async def cb_title(call: CallbackQuery, state: FSMContext):
    val = call.data[len("adm:title:"):]
    if val == "custom":
        await call.message.edit_text("Введи название занятия:")
        await call.answer()
        return
    await state.update_data(title=val)
    await state.set_state(AddClassFSM.trainer)
    await call.message.edit_text(
        "📅 <b>Шаг 2/4 — тренер</b>\n\nВыбери тренера:",
        reply_markup=trainers_kb(),
    )
    await call.answer()

@router.message(AddClassFSM.title)
async def msg_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddClassFSM.trainer)
    await message.answer(
        "📅 <b>Шаг 2/4 — тренер</b>\n\nВыбери тренера:",
        reply_markup=trainers_kb(),
    )

# Шаг 2 — тренер
@router.callback_query(F.data.startswith("adm:trainer:"), AddClassFSM.trainer)
async def cb_trainer(call: CallbackQuery, state: FSMContext):
    val = call.data[len("adm:trainer:"):]
    if val == "custom":
        await call.message.edit_text("Введи имя тренера:")
        await call.answer()
        return
    await state.update_data(trainer=val)
    await state.set_state(AddClassFSM.date_time)
    await call.message.edit_text(
        "📅 <b>Шаг 3/4 — дата и время</b>\n\n"
        "Введи в формате: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
        "<i>Пример: 10.04.2025 09:00</i>"
    )
    await call.answer()

@router.message(AddClassFSM.trainer)
async def msg_trainer(message: Message, state: FSMContext):
    await state.update_data(trainer=message.text.strip())
    await state.set_state(AddClassFSM.date_time)
    await message.answer(
        "📅 <b>Шаг 3/4 — дата и время</b>\n\n"
        "Введи в формате: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
        "<i>Пример: 10.04.2025 09:00</i>"
    )

# Шаг 3 — дата
@router.message(AddClassFSM.date_time)
async def msg_datetime(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Пример: <code>10.04.2025 09:00</code>")
        return
    if dt < datetime.now():
        await message.answer("❌ Это время уже прошло. Введи другую дату:")
        return
    await state.update_data(starts_at=dt)
    await state.set_state(AddClassFSM.max_spots)
    await message.answer(
        "📅 <b>Шаг 4/4 — количество мест</b>\n\nВыбери или введи число:",
        reply_markup=spots_kb(),
    )

# Шаг 4 — места
@router.callback_query(F.data.startswith("adm:spots:"), AddClassFSM.max_spots)
async def cb_spots(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    spots = int(call.data[len("adm:spots:"):])
    await _save_class(call.message, state, session, spots, edit=True)
    await call.answer()

@router.message(AddClassFSM.max_spots)
async def msg_spots(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text.strip().isdigit():
        await message.answer("❌ Введи число, например: 8")
        return
    await _save_class(message, state, session, int(message.text.strip()), edit=False)

async def _save_class(msg, state: FSMContext, session: AsyncSession, spots: int, edit: bool):
    data = await state.get_data()
    await state.clear()
    cls = await create_class(
        session,
        title=data["title"],
        trainer=data["trainer"],
        starts_at=data["starts_at"],
        max_spots=spots,
    )
    b = InlineKeyboardBuilder()
    b.button(text="📅 Ещё занятие", callback_data="adm:addclass")
    b.button(text="🏠 В меню",      callback_data="adm:main")
    b.adjust(2)
    text = (
        f"✅ <b>Занятие добавлено!</b>\n\n"
        f"🧘 {cls.title}\n"
        f"📅 {cls.starts_at.strftime('%d.%m.%Y в %H:%M')}\n"
        f"👤 {cls.trainer}\n"
        f"👥 Мест: {cls.max_spots}"
    )
    if edit:
        await msg.edit_text(text, reply_markup=b.as_markup())
    else:
        await msg.answer(text, reply_markup=b.as_markup())

# ═══════════════════════════════════════════════════════════════
# РАСПИСАНИЕ (просмотр + отмена занятия)
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:schedule")
async def cb_schedule(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    now   = datetime.now()
    until = now + timedelta(days=14)
    result = await session.execute(
        select(Class).where(
            Class.starts_at >= now,
            Class.starts_at <= until,
            Class.is_cancelled == False,
        ).order_by(Class.starts_at)
    )
    classes = result.scalars().all()

    b = InlineKeyboardBuilder()
    if not classes:
        b.button(text="📅 Добавить занятие", callback_data="adm:addclass")
        b.button(text="◀️ Назад",            callback_data="adm:main")
        b.adjust(1)
        await call.message.edit_text("На ближайшие 2 недели занятий нет.", reply_markup=b.as_markup())
        await call.answer()
        return

    for cls in classes:
        cnt = await session.scalar(
            select(func.count(Booking.id)).where(
                Booking.class_id == cls.id,
                Booking.status == BookingStatus.CONFIRMED,
            )
        ) or 0
        b.button(
            text=f"{cls.starts_at.strftime('%d.%m %H:%M')} {cls.title[:18]} ({cnt}/{cls.max_spots})",
            callback_data=f"adm:cls:{cls.id}",
        )
    b.button(text="📅 Добавить", callback_data="adm:addclass")
    b.button(text="◀️ Назад",    callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text(
        "📋 <b>Расписание — 14 дней</b>\n\nНажми на занятие для управления:",
        reply_markup=b.as_markup(),
    )
    await call.answer()

@router.callback_query(F.data.startswith("adm:cls:"))
async def cb_class_detail(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    cls_id = int(call.data[len("adm:cls:"):])
    cls = await session.get(Class, cls_id)
    if not cls:
        await call.answer("Не найдено", show_alert=True)
        return

    result = await session.execute(
        select(Booking, User).join(User, Booking.user_id == User.id).where(
            Booking.class_id == cls_id,
            Booking.status == BookingStatus.CONFIRMED,
        )
    )
    rows = result.all()
    names = "\n".join(f"  • {u.full_name}" for _, u in rows) if rows else "  (никто не записан)"

    b = InlineKeyboardBuilder()
    b.button(text="❌ Отменить занятие", callback_data=f"adm:cancel_cls:{cls_id}")
    b.button(text="◀️ К расписанию",    callback_data="adm:schedule")
    b.adjust(1)

    await call.message.edit_text(
        f"📌 <b>{cls.title}</b>\n"
        f"📅 {cls.starts_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"👤 {cls.trainer}\n"
        f"👥 Записей: {len(rows)}/{cls.max_spots}\n\n"
        f"{names}",
        reply_markup=b.as_markup(),
    )
    await call.answer()

@router.callback_query(F.data.startswith("adm:cancel_cls:"))
async def cb_cancel_class(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    cls_id = int(call.data[len("adm:cancel_cls:"):])
    cls = await session.get(Class, cls_id)
    if not cls:
        await call.answer("Не найдено", show_alert=True)
        return

    result = await session.execute(
        select(Booking).where(
            Booking.class_id == cls_id,
            Booking.status == BookingStatus.CONFIRMED,
        )
    )
    bookings = result.scalars().all()
    for bk in bookings:
        bk.status = BookingStatus.CANCELLED
        try:
            await call.bot.send_message(
                bk.user_id,
                f"❌ <b>Занятие отменено</b>\n\n"
                f"{cls.title} — {cls.starts_at.strftime('%d.%m в %H:%M')}\n\n"
                f"Извини за неудобство! Место освобождено. 🙏"
            )
        except Exception:
            pass

    cls.is_cancelled = True
    await session.commit()

    b = InlineKeyboardBuilder()
    b.button(text="◀️ К расписанию", callback_data="adm:schedule")
    b.adjust(1)
    await call.message.edit_text(
        f"✅ Занятие отменено. Уведомлено клиентов: {len(bookings)}",
        reply_markup=b.as_markup(),
    )
    await call.answer()

# ═══════════════════════════════════════════════════════════════
# КЛИЕНТЫ
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm:clients:"))
async def cb_clients(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    page = int(call.data[len("adm:clients:"):])
    result = await session.execute(
        select(User).where(User.is_active == True)
        .order_by(User.full_name)
        .offset(page * PAGE_SIZE).limit(PAGE_SIZE + 1)
    )
    users = result.scalars().all()
    has_next = len(users) > PAGE_SIZE
    users = users[:PAGE_SIZE]
    total = await session.scalar(select(func.count(User.id)).where(User.is_active == True)) or 0

    b = InlineKeyboardBuilder()
    for u in users:
        has_sub = await session.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.user_id == u.id,
                Subscription.classes_left > 0,
            )
        ) or 0
        icon = "✅" if has_sub else "⚠️"
        b.button(text=f"{icon} {u.full_name[:26]}", callback_data=f"adm:user:{u.id}")

    if page > 0:
        b.button(text="◀ Пред.", callback_data=f"adm:clients:{page - 1}")
    if has_next:
        b.button(text="След. ▶", callback_data=f"adm:clients:{page + 1}")
    b.button(text="🏠 Меню", callback_data="adm:main")
    b.adjust(1)

    await call.message.edit_text(
        f"👥 <b>Клиенты</b> — {total} чел.\n✅ с абонементом  ⚠️ без",
        reply_markup=b.as_markup(),
    )
    await call.answer()

@router.callback_query(F.data.startswith("adm:user:"))
async def cb_user_card(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:user:"):])
    u = await session.get(User, uid)
    if not u:
        await call.answer("Не найдено", show_alert=True)
        return

    sub = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == uid, Subscription.classes_left > 0
        ).order_by(Subscription.expires_at)
    )
    missed = await session.scalar(
        select(func.count(Booking.id)).where(
            Booking.user_id == uid, Booking.status == BookingStatus.MISSED
        )
    ) or 0
    total_bk = await session.scalar(
        select(func.count(Booking.id)).where(Booking.user_id == uid)
    ) or 0

    sub_text = (
        f"✅ Абонемент: {sub.classes_left} зан."
        + (f" · до {sub.expires_at.strftime('%d.%m')}" if sub and sub.expires_at else "")
        if sub else "⚠️ Абонемента нет"
    )

    b = InlineKeyboardBuilder()
    b.button(text="➕ Начислить занятия",  callback_data=f"adm:give:{uid}")
    b.button(text="🔥 Пнуть",             callback_data=f"adm:kick:{uid}")
    b.button(text="📋 История записей",   callback_data=f"adm:bkhistory:{uid}")
    b.button(text="🚫 Заблокировать",     callback_data=f"adm:block:{uid}")
    b.button(text="◀️ К списку",          callback_data="adm:clients:0")
    b.adjust(2, 2, 1)

    await call.message.edit_text(
        f"👤 <b>{u.full_name}</b>\n"
        f"@{u.username or '—'}  ·  <code>{u.id}</code>\n\n"
        f"{sub_text}\n"
        f"Занятий всего: {total_bk}  ·  пропусков: {missed}",
        reply_markup=b.as_markup(),
    )
    await call.answer()

@router.callback_query(F.data.startswith("adm:give:"))
async def cb_give(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:give:"):])
    b = InlineKeyboardBuilder()
    for n in [1, 2, 4, 8]:
        b.button(text=f"+{n}", callback_data=f"adm:gn:{uid}:{n}")
    b.button(text="◀️ Назад", callback_data=f"adm:user:{uid}")
    b.adjust(4, 1)
    await call.message.edit_text(
        "➕ <b>Начислить занятия</b>\n\nСколько занятий добавить клиенту?",
        reply_markup=b.as_markup(),
    )
    await call.answer()

@router.callback_query(F.data.startswith("adm:gn:"))
async def cb_give_n(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    parts = call.data.split(":")  # adm, gn, uid, n
    uid, n = int(parts[2]), int(parts[3])
    u = await session.get(User, uid)

    sub = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == uid, Subscription.classes_left > 0
        )
    )
    if sub:
        sub.classes_left += n
    else:
        sub = Subscription(
            user_id=uid,
            sub_type=SubscriptionType.SINGLE,
            classes_left=n,
            expires_at=datetime.now() + timedelta(days=90),
        )
        session.add(sub)
    await session.commit()

    try:
        await call.bot.send_message(
            uid,
            f"🎁 Тебе начислено <b>{n} занятий</b> от администратора!\n"
            f"Записывайся: /schedule"
        )
    except Exception:
        pass

    b = InlineKeyboardBuilder()
    b.button(text="◀️ К клиенту", callback_data=f"adm:user:{uid}")
    b.adjust(1)
    await call.message.edit_text(
        f"✅ +{n} занятий начислено для <b>{u.full_name}</b>",
        reply_markup=b.as_markup(),
    )
    await call.answer()

@router.callback_query(F.data.startswith("adm:kick:"))
async def cb_kick(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:kick:"):])
    u = await session.get(User, uid)
    try:
        await call.bot.send_message(
            uid,
            f"👋 <b>Привет, {u.full_name.split()[0]}!</b>\n\n"
            f"Давно тебя не было — скучаем! Возвращайся на пилатес 🧘\n"
            f"Посмотреть расписание: /schedule"
        )
        await call.answer(f"✅ Пинок отправлен!", show_alert=True)
    except Exception:
        await call.answer("❌ Клиент заблокировал бота", show_alert=True)

@router.callback_query(F.data.startswith("adm:block:"))
async def cb_block(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:block:"):])
    u = await session.get(User, uid)
    u.is_active = False
    await session.commit()
    await call.answer(f"🚫 {u.full_name} заблокирован", show_alert=True)
    # Возвращаемся к карточке
    call.data = f"adm:user:{uid}"
    await cb_user_card(call, session)

@router.callback_query(F.data.startswith("adm:bkhistory:"))
async def cb_bk_history(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:bkhistory:"):])
    result = await session.execute(
        select(Booking, Class)
        .join(Class, Booking.class_id == Class.id)
        .where(Booking.user_id == uid)
        .order_by(Class.starts_at.desc())
        .limit(10)
    )
    rows = result.all()
    STATUS = {
        BookingStatus.CONFIRMED: "✅",
        BookingStatus.CANCELLED: "❌",
        BookingStatus.MISSED:    "😔",
        BookingStatus.ATTENDED:  "✔️",
    }
    lines = [
        f"{STATUS.get(bk.status, '?')} {cls.starts_at.strftime('%d.%m %H:%M')} {cls.title[:20]}"
        for bk, cls in rows
    ] or ["Записей нет"]

    b = InlineKeyboardBuilder()
    b.button(text="◀️ Назад", callback_data=f"adm:user:{uid}")
    b.adjust(1)
    await call.message.edit_text(
        "<b>История записей (последние 10):</b>\n\n" + "\n".join(lines),
        reply_markup=b.as_markup(),
    )
    await call.answer()

# ═══════════════════════════════════════════════════════════════
# ПЛАТЕЖИ
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:payments")
async def cb_payments(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    month_total = await session.scalar(
        select(func.sum(Payment.amount)).where(
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.paid_at >= month_start,
        )
    ) or 0

    result = await session.execute(
        select(Payment, User)
        .join(User, Payment.user_id == User.id)
        .where(Payment.status == PaymentStatus.SUCCEEDED)
        .order_by(Payment.paid_at.desc())
        .limit(15)
    )
    rows = result.all()

    lines = [f"💰 <b>Платежи</b>  ·  месяц: <b>{month_total} ₽</b>\n"]
    for pay, u in rows:
        dt = pay.paid_at.strftime("%d.%m %H:%M") if pay.paid_at else "—"
        lines.append(f"{dt}  {u.full_name[:20]}  <b>{pay.amount} ₽</b>")

    b = InlineKeyboardBuilder()
    b.button(text="◀️ Меню", callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text("\n".join(lines), reply_markup=b.as_markup())
    await call.answer()

# ═══════════════════════════════════════════════════════════════
# СТАТИСТИКА
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:stats")
async def cb_stats(call: CallbackQuery, session: AsyncSession):
    if not await check_admin(call):
        return
    total_users  = await session.scalar(select(func.count(User.id)).where(User.is_active == True)) or 0
    total_cls    = await session.scalar(select(func.count(Class.id)).where(Class.is_cancelled == False)) or 0
    total_bk     = await session.scalar(select(func.count(Booking.id))) or 0
    missed       = await session.scalar(select(func.count(Booking.id)).where(Booking.status == BookingStatus.MISSED)) or 0
    active_subs  = await session.scalar(select(func.count(Subscription.id)).where(Subscription.classes_left > 0)) or 0
    total_income = await session.scalar(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.SUCCEEDED)) or 0
    miss_pct     = round(missed / total_bk * 100) if total_bk else 0

    b = InlineKeyboardBuilder()
    b.button(text="◀️ Меню", callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text(
        f"📊 <b>Статистика студии</b>\n\n"
        f"👥 Клиентов: {total_users}\n"
        f"📋 Активных абонементов: {active_subs}\n\n"
        f"📅 Занятий в расписании: {total_cls}\n"
        f"✅ Записей всего: {total_bk}\n"
        f"😔 Пропусков: {missed} ({miss_pct}%)\n\n"
        f"💰 Общий доход: <b>{total_income} ₽</b>",
        reply_markup=b.as_markup(),
    )
    await call.answer()

# ═══════════════════════════════════════════════════════════════
# РАССЫЛКА
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not await check_admin(call):
        return
    await state.set_state(BroadcastFSM.text)
    await call.message.edit_text(
        "📣 <b>Рассылка всем клиентам</b>\n\n"
        "Введи текст. Поддерживается HTML:\n"
        "<b>жирный</b>  <i>курсив</i>  <a href='...'>ссылка</a>"
    )
    await call.answer()

@router.message(BroadcastFSM.text)
async def msg_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(BroadcastFSM.confirm)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить всем", callback_data="adm:bcast_go")
    b.button(text="❌ Отмена",         callback_data="adm:main")
    b.adjust(1)
    await message.answer(
        f"📣 <b>Предпросмотр:</b>\n\n{message.text}\n\n─────\nОтправить всем клиентам?",
        reply_markup=b.as_markup(),
    )

@router.callback_query(F.data == "adm:bcast_go", BroadcastFSM.confirm)
async def cb_broadcast_go(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await check_admin(call):
        return
    data = await state.get_data()
    await state.clear()
    text  = data.get("text", "")
    users = await get_all_active_users(session)
    await call.message.edit_text(f"⏳ Отправляю {len(users)} клиентам...")
    sent, failed = 0, 0
    for u in users:
        try:
            await call.bot.send_message(u.id, text)
            sent += 1
        except Exception:
            failed += 1
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Меню", callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text(
        f"📣 <b>Рассылка завершена!</b>\n\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
        reply_markup=b.as_markup(),
    )
    await call.answer()
