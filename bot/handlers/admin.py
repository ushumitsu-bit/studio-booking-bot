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
from db.models import (
    Booking, BookingStatus, Class, Payment,
    PaymentStatus, Subscription, SubscriptionType, User,
)
from db.queries import create_class, get_all_active_users
import logging
import calendar as cal_module

MONTHS_RU = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
DAYS_SHORT_CAL = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]

router = Router()
logger = logging.getLogger(__name__)

def calendar_kb(year: int, month: int):
    b = InlineKeyboardBuilder()
    prev_m = month - 1 if month > 1 else 12
    prev_y = year if month > 1 else year - 1
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1
    b.button(text="◀", callback_data=f"adm:cal:{prev_y}:{prev_m}")
    b.button(text=f"{MONTHS_RU[month-1]} {year}", callback_data="adm:cal:ignore")
    b.button(text="▶", callback_data=f"adm:cal:{next_y}:{next_m}")
    for d in DAYS_SHORT_CAL:
        b.button(text=d, callback_data="adm:cal:ignore")
    now = datetime.now()
    first_weekday, days_in_month = cal_module.monthrange(year, month)
    for _ in range(first_weekday):
        b.button(text=" ", callback_data="adm:cal:ignore")
    for day in range(1, days_in_month + 1):
        d = datetime(year, month, day)
        if d.date() < now.date():
            b.button(text="·", callback_data="adm:cal:ignore")
        elif d.date() == now.date():
            b.button(text=f"[{day}]", callback_data=f"adm:calday:{year}:{month}:{day}")
        else:
            b.button(text=str(day), callback_data=f"adm:calday:{year}:{month}:{day}")
    total = first_weekday + days_in_month
    remainder = total % 7
    if remainder:
        for _ in range(7 - remainder):
            b.button(text=" ", callback_data="adm:cal:ignore")
    b.button(text="← Назад", callback_data="adm:addclass")
    b.adjust(3, 7, 7, 7, 7, 7, 7, 7, 7, 1)
    return b.as_markup()

def times_kb_inline():
    b = InlineKeyboardBuilder()
    times = ["08:00","09:00","10:00","11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00","19:00","20:00","21:00"]
    for t in times:
        b.button(text=t, callback_data=f"adm:time:{t}")
    b.button(text="✏️ Другое время", callback_data="adm:time:manual")
    b.adjust(4, 4, 4, 4, 1)
    return b.as_markup()

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

class AddClassFSM(StatesGroup):
    title        = State()
    trainer      = State()
    date_time    = State()
    max_spots    = State()
    location     = State()
    payment_type = State()

class SettingsFSM(StatesGroup):
    edit_key  = State()
    edit_value = State()

class BroadcastFSM(StatesGroup):
    text    = State()
    confirm = State()

PAGE_SIZE = 8

def _split_setting(val: str) -> list[str]:
    return [x.strip() for x in val.split("|") if x.strip()]

async def build_main_text(session):
    today_start = datetime.now().replace(hour=0, minute=0, second=0)
    today_end = today_start + timedelta(days=1)
    total_users = await session.scalar(select(func.count(User.id)).where(User.is_active == True)) or 0
    today_classes = await session.scalar(select(func.count(Class.id)).where(Class.starts_at >= today_start, Class.starts_at < today_end, Class.is_cancelled == False)) or 0
    active_sub_ids = select(Subscription.user_id).where(Subscription.classes_left > 0)
    no_sub = await session.scalar(select(func.count(User.id)).where(User.is_active == True, User.id.not_in(active_sub_ids))) or 0
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    month_income = await session.scalar(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.SUCCEEDED, Payment.paid_at >= month_start)) or 0
    return (
        f"🛠 <b>Панель администратора</b>\n\n"
        f"👥 Клиентов: <b>{total_users}</b>  ·  без абонемента: <b>{no_sub}</b>\n"
        f"📅 Занятий сегодня: <b>{today_classes}</b>\n"
        f"💰 Доход за месяц: <b>{month_income:,} сум</b>"
    )

def main_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📅 Добавить занятие", callback_data="adm:addclass")
    b.button(text="📋 Расписание",        callback_data="adm:schedule")
    b.button(text="👥 Клиенты",           callback_data="adm:clients:0")
    b.button(text="💰 Платежи",           callback_data="adm:payments")
    b.button(text="📣 Рассылка",          callback_data="adm:broadcast")
    b.button(text="📊 Статистика",        callback_data="adm:stats")
    b.button(text="⚙️ Настройки",         callback_data="adm:settings")
    b.adjust(1, 2, 2, 1, 1)
    return b.as_markup()


@router.message(Command("help"))
async def cmd_help(message: Message, **kwargs):
    if not is_admin(message.from_user.id):
        return
    text = (
        "📖 <b>Инструкция администратора</b>\n\n"
        "<b>/admin</b> — открыть панель\n\n"
        "📅 <b>Добавить занятие</b> — 6 шагов:\n"
        "название → тренер → дата → время → места → место/оплата\n\n"
        "💳 <i>Через бота</i> — онлайн оплата Payme\n"
        "🏢 <i>Через студию</i> — только инфо, без оплаты\n\n"
        "📋 <b>Расписание</b> — занятия на 14 дней, список клиентов, отмена\n\n"
        "👥 <b>Клиенты</b>\n"
        "✅ есть абонемент  ⚠️ нет абонемента\n"
        "➕ начислить занятия (оплата наличными)\n"
        "🔥 пнуть — мотивационное сообщение\n\n"
        "💰 <b>Платежи</b> — история оплат через Payme\n\n"
        "📣 <b>Рассылка</b> — сообщение всем клиентам\n\n"
        "⏰ <b>Автоуведомления</b> работают сами:\n"
        "• за 24 ч и 2 ч до занятия\n"
        "• пинок за пропуск\n"
        "• предупреждение об абонементе"
    )
    await message.answer(text)

@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, **kwargs):
    if not await check_admin(message):
        return
    text = await build_main_text(session)
    await message.answer(text, reply_markup=main_menu_kb())

@router.callback_query(F.data == "adm:main")
async def cb_admin_main(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    text = await build_main_text(session)
    await call.message.edit_text(text, reply_markup=main_menu_kb())
    await call.answer()

def templates_kb(items: list[str]):
    b = InlineKeyboardBuilder()
    for t in items:
        b.button(text=t, callback_data=f"adm:title:{t[:40]}")
    b.button(text="✏️ Своё название", callback_data="adm:title:custom")
    b.button(text="← Меню",         callback_data="adm:main")
    b.adjust(1)
    return b.as_markup()

def trainers_kb(items: list[str]):
    b = InlineKeyboardBuilder()
    for t in items:
        b.button(text=t, callback_data=f"adm:trainer:{t}")
    b.button(text="✏️ Другой тренер", callback_data="adm:trainer:custom")
    b.button(text="◀️ Назад",         callback_data="adm:addclass")
    b.adjust(1)
    return b.as_markup()
def spots_kb():
    b = InlineKeyboardBuilder()
    for n in [5, 8, 10, 12, 15, 18, 20, 25]:
        b.button(text=str(n), callback_data=f"adm:spots:{n}")
    b.button(text="✏️ Другое", callback_data="adm:spots:custom")
    b.adjust(4, 4, 1)
    return b.as_markup()

def location_kb(items: list[str]):
    b = InlineKeyboardBuilder()
    for loc in items:
        b.button(text=loc, callback_data=f"adm:loc:{loc}")
    b.button(text="✏️ Другое место", callback_data="adm:loc:custom")
    b.adjust(1)
    return b.as_markup()

def payment_type_kb():
    b = InlineKeyboardBuilder()
    b.button(text="💳 Через бота (Payme)", callback_data="adm:paytype:bot")
    b.button(text="🏢 Через студию (только инфо)", callback_data="adm:paytype:studio")
    b.adjust(1)
    return b.as_markup()

@router.callback_query(F.data == "adm:addclass")
async def cb_addclass(call: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    from db.queries import get_setting
    templates = _split_setting(await get_setting(session, "class_templates"))
    await state.clear()
    await state.set_state(AddClassFSM.title)
    await call.message.edit_text("📅 <b>Добавить занятие — шаг 1/6</b>\n\nВыбери название:", reply_markup=templates_kb(templates))
    await call.answer()
@router.callback_query(F.data.startswith("adm:title:"), AddClassFSM.title)
async def cb_title(call: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs):
    val = call.data[len("adm:title:"):]
    if val == "custom":
        await call.message.edit_text("Введи название занятия:")
        await call.answer()
        return
    from db.queries import get_setting
    trainers = _split_setting(await get_setting(session, "trainers"))
    await state.update_data(title=val)
    await state.set_state(AddClassFSM.trainer)
    await call.message.edit_text("📅 <b>Шаг 2/6 — тренер</b>\n\nВыбери тренера:", reply_markup=trainers_kb(trainers))
    await call.answer()

@router.message(AddClassFSM.title)
async def msg_title(message: Message, state: FSMContext, session: AsyncSession, **kwargs):
    from db.queries import get_setting
    trainers = _split_setting(await get_setting(session, "trainers"))
    await state.update_data(title=message.text.strip())
    await state.set_state(AddClassFSM.trainer)
    await message.answer("📅 <b>Шаг 2/6 — тренер</b>\n\nВыбери тренера:", reply_markup=trainers_kb(trainers))

@router.callback_query(F.data.startswith("adm:trainer:"), AddClassFSM.trainer)
async def cb_trainer(call: CallbackQuery, state: FSMContext, **kwargs):
    val = call.data[len("adm:trainer:"):]
    if val == "custom":
        await call.message.edit_text("Введи имя тренера:")
        await call.answer()
        return
    await state.update_data(trainer=val)
    await state.set_state(AddClassFSM.date_time)
    now = datetime.now()
    await call.message.edit_text("📅 <b>Шаг 3/6 — выбери дату</b>\n\n[день] = сегодня  · = прошедшие дни", reply_markup=calendar_kb(now.year, now.month))
    await call.answer()
@router.message(AddClassFSM.trainer)
async def msg_trainer(message: Message, state: FSMContext, **kwargs):
    await state.update_data(trainer=message.text.strip())
    await state.set_state(AddClassFSM.date_time)
    now = datetime.now()
    await message.answer("📅 <b>Шаг 3/6 — выбери дату</b>\n\n[день] = сегодня  · = прошедшие дни", reply_markup=calendar_kb(now.year, now.month))



@router.callback_query(F.data == "adm:cal:ignore")
async def cb_cal_ignore(call: CallbackQuery, **kwargs):
    await call.answer()

@router.callback_query(F.data.startswith("adm:cal:"), AddClassFSM.date_time)
async def cb_cal_nav(call: CallbackQuery, **kwargs):
    parts = call.data.split(":")
    year, month = int(parts[2]), int(parts[3])
    await call.message.edit_text("📅 <b>Шаг 3/6 — выбери дату</b>\n\n[день] = сегодня  · = прошедшие дни", reply_markup=calendar_kb(year, month))
    await call.answer()

@router.callback_query(F.data.startswith("adm:calday:"), AddClassFSM.date_time)
async def cb_cal_day(call: CallbackQuery, state: FSMContext, **kwargs):
    parts = call.data.split(":")
    year, month, day = int(parts[2]), int(parts[3]), int(parts[4])
    date_str = f"{day:02d}.{month:02d}.{year}"
    await state.update_data(date_part=date_str)
    await call.message.edit_text(
        f"📅 Дата: <b>{date_str}</b>\n\n🕐 <b>Выбери время занятия:</b>",
        reply_markup=times_kb_inline()
    )
    await call.answer()

@router.callback_query(F.data.startswith("adm:time:"), AddClassFSM.date_time)
async def cb_time_inline(call: CallbackQuery, state: FSMContext, **kwargs):
    val = call.data[len("adm:time:"):]
    data = await state.get_data()
    date_part = data.get("date_part", "")
    if val == "manual":
        await call.message.edit_text(f"📅 Дата: <b>{date_part}</b>\n\nВведи время в формате <code>ЧЧ:ММ</code>\n<i>Пример: 09:30</i>")
        await call.answer()
        return
    from datetime import datetime as _dt
    dt = _dt.strptime(f"{date_part} {val}", "%d.%m.%Y %H:%M")
    await state.update_data(starts_at=dt.isoformat())
    await state.set_state(AddClassFSM.max_spots)
    await call.message.edit_text(
        f"✅ <b>{date_part} в {val}</b>\n\n📅 <b>Шаг 4/6 — количество мест</b>\n\nВыбери:",
        reply_markup=spots_kb()
    )
    await call.answer()

@router.message(AddClassFSM.date_time)
async def msg_datetime(message: Message, state: FSMContext, **kwargs):
    text = message.text.strip()
    data = await state.get_data()
    date_part = data.get("date_part")
    
    # Если уже есть дата — ждём только время
    if date_part and len(text) <= 5:
        try:
            dt = datetime.strptime(f"{date_part} {text}", "%d.%m.%Y %H:%M")
        except ValueError:
            await message.answer("❌ Неверный формат времени. Пример: <code>09:00</code>")
            return
    else:
        try:
            dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
        except ValueError:
            await message.answer("❌ Неверный формат. Пример: <code>10.04.2025 09:00</code>")
            return
    if dt < datetime.now():
        await message.answer("❌ Это время уже прошло. Введи другую дату:")
        return
    await state.update_data(starts_at=dt.isoformat())
    await state.set_state(AddClassFSM.max_spots)
    await message.answer(f"✅ <b>{dt.strftime('%d.%m.%Y в %H:%M')}</b>\n\n📅 <b>Шаг 4/6 — количество мест</b>\n\nВыбери:", reply_markup=spots_kb())

@router.callback_query(F.data.startswith("adm:spots:"), AddClassFSM.max_spots)
async def cb_spots(call: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs):
    val = call.data[len("adm:spots:"):]
    if val == "custom":
        await call.message.edit_text("Введи количество мест:")
        await call.answer()
        return
    from db.queries import get_setting
    locations = _split_setting(await get_setting(session, "locations"))
    await state.update_data(spots=int(val))
    await state.set_state(AddClassFSM.location)
    await call.message.edit_text("📍 <b>Шаг 5/6 — место проведения</b>\n\nГде будет занятие?", reply_markup=location_kb(locations))
    await call.answer()

@router.message(AddClassFSM.max_spots)
async def msg_spots(message: Message, state: FSMContext, session: AsyncSession, **kwargs):
    if not message.text.strip().isdigit():
        await message.answer("❌ Введи число, например: 8")
        return
    from db.queries import get_setting
    locations = _split_setting(await get_setting(session, "locations"))
    await state.update_data(spots=int(message.text.strip()))
    await state.set_state(AddClassFSM.location)
    await message.answer("📍 <b>Шаг 5/6 — место проведения</b>\n\nГде будет занятие?", reply_markup=location_kb(locations))

@router.callback_query(F.data.startswith("adm:loc:"), AddClassFSM.location)
async def cb_location(call: CallbackQuery, state: FSMContext, **kwargs):
    val = call.data[len("adm:loc:"):]
    if val == "custom":
        await call.message.edit_text("Введи название места/студии:")
        await call.answer()
        return
    await state.update_data(location=val)
    await state.set_state(AddClassFSM.payment_type)
    await call.message.edit_text(
        f"💳 <b>Шаг 6/6 — способ оплаты</b>\n\nМесто: {val}\n\nКак клиенты будут оплачивать?",
        reply_markup=payment_type_kb(),
    )
    await call.answer()

@router.message(AddClassFSM.location)
async def msg_location(message: Message, state: FSMContext, **kwargs):
    await state.update_data(location=message.text.strip())
    await state.set_state(AddClassFSM.payment_type)
    await message.answer("💳 <b>Шаг 6/6 — способ оплаты</b>\n\nКак клиенты будут оплачивать?", reply_markup=payment_type_kb())

@router.callback_query(F.data.startswith("adm:paytype:"), AddClassFSM.payment_type)
async def cb_payment_type(call: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs):
    val = call.data[len("adm:paytype:"):]
    payment_enabled = val == "bot"
    await state.update_data(payment_enabled=payment_enabled, booking_enabled=True)
    data = await state.get_data()
    await _save_class(call.message, state, session, data.get("spots", 8), edit=True)
    await call.answer()

async def _save_class(msg, state, session, spots, edit):
    data = await state.get_data()
    await state.clear()
    from datetime import datetime as _dt
    location = data.get("location", "Студия")
    payment_enabled = data.get("payment_enabled", True)
    booking_enabled = data.get("booking_enabled", True)
    cls = await create_class(session, title=data["title"], trainer=data["trainer"], starts_at=_dt.fromisoformat(data["starts_at"]), max_spots=spots, location=location, payment_enabled=payment_enabled, booking_enabled=booking_enabled)
    pay_label = "💳 через бота" if payment_enabled else "🏢 через студию"
    b = InlineKeyboardBuilder()
    b.button(text="📅 Ещё занятие", callback_data="adm:addclass")
    b.button(text="← Меню",      callback_data="adm:main")
    b.adjust(2)
    text = f"✅ <b>Занятие добавлено!</b>\n\n🧘 {cls.title}\n📅 {cls.starts_at.strftime('%d.%m.%Y в %H:%M')}\n👤 {cls.trainer}\n📍 {cls.location}\n💳 Оплата: {pay_label}\n👥 Мест: {cls.max_spots}"
    if edit:
        await msg.edit_text(text, reply_markup=b.as_markup())
    else:
        await msg.answer(text, reply_markup=b.as_markup())

@router.callback_query(F.data == "adm:schedule")
async def cb_schedule(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    now = datetime.now()
    since = now - timedelta(days=1)
    result = await session.execute(select(Class).where(Class.starts_at >= since, Class.starts_at <= now + timedelta(days=30), Class.is_cancelled == False).order_by(Class.starts_at))
    classes = result.scalars().all()
    b = InlineKeyboardBuilder()
    if not classes:
        b.button(text="📅 Добавить занятие", callback_data="adm:addclass")
        b.button(text="← Меню", callback_data="adm:main")
        b.adjust(1)
        await call.message.edit_text("Занятий нет (вчера — 30 дней вперёд).", reply_markup=b.as_markup())
        await call.answer()
        return
    for cls in classes:
        cnt = await session.scalar(select(func.count(Booking.id)).where(Booking.class_id == cls.id, Booking.status == BookingStatus.CONFIRMED)) or 0
        pay_icon = "💳" if getattr(cls, "payment_enabled", True) else "🏢"
        b.button(text=f"{pay_icon} {cls.starts_at.strftime('%d.%m %H:%M')} {cls.title[:15]} ({cnt}/{cls.max_spots})", callback_data=f"adm:cls:{cls.id}")
    b.button(text="📅 Добавить", callback_data="adm:addclass")
    b.button(text="← Меню",    callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text("📋 <b>Расписание — 14 дней</b>\n\n💳 = через бота  🏢 = через студию", reply_markup=b.as_markup())
    await call.answer()

@router.callback_query(F.data.startswith("adm:cls:"))
async def cb_class_detail(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    cls_id = int(call.data[len("adm:cls:"):])
    await _show_class_detail(call, session, cls_id)

async def _show_class_detail(call: CallbackQuery, session: AsyncSession, cls_id: int):
    cls = await session.get(Class, cls_id)
    if not cls:
        await call.answer("Не найдено", show_alert=True)
        return

    result = await session.execute(
        select(Booking, User)
        .join(User, Booking.user_id == User.id)
        .where(Booking.class_id == cls_id, Booking.status.in_([
            BookingStatus.CONFIRMED, BookingStatus.ATTENDED
        ]))
    )
    rows = result.all()

    STATUS_ICON = {BookingStatus.CONFIRMED: "⬜", BookingStatus.ATTENDED: "✅"}
    attended = sum(1 for bk, _ in rows if bk.status == BookingStatus.ATTENDED)
    confirmed = sum(1 for bk, _ in rows if bk.status == BookingStatus.CONFIRMED)

    roster = "\n".join(
        f"  {STATUS_ICON.get(bk.status,'⬜')} {u.full_name}"
        for bk, u in rows
    ) if rows else "  (никто не записан)"

    pay_label = "💳 через бота" if getattr(cls, "payment_enabled", True) else "🏢 через студию"
    location  = getattr(cls, "location", "—")

    b = InlineKeyboardBuilder()
    b.button(text="📱 QR явка",          callback_data=f"adm:qr:{cls_id}")
    b.button(text="✅ Отметить вручную", callback_data=f"adm:roster:{cls_id}")
    b.button(text="❌ Отменить занятие", callback_data=f"adm:cancel_cls:{cls_id}")
    b.button(text="← Расписание",       callback_data="adm:schedule")
    b.adjust(2, 1, 1)

    await call.message.edit_text(
        f"📌 <b>{cls.title}</b>\n"
        f"📅 {cls.starts_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"👤 {cls.trainer} · 📍 {location}\n"
        f"💳 {pay_label}\n"
        f"👥 Всего: {len(rows)}/{cls.max_spots}  ·  ✅ пришли: {attended}  ·  ⬜ ожидаем: {confirmed}\n\n"
        f"{roster}",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:qr:"))
async def cb_class_qr(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    from services.attendance import qr_url
    import qrcode, io
    from aiogram.types import BufferedInputFile

    cls_id = int(call.data[len("adm:qr:"):])
    cls = await session.get(Class, cls_id)
    if not cls:
        await call.answer("Не найдено", show_alert=True)
        return

    url = qr_url(cls_id)
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    await call.answer()
    await call.message.answer_photo(
        BufferedInputFile(buf.read(), filename="qr.png"),
        caption=(
            f"📱 <b>QR для явки</b>\n\n"
            f"🧘 {cls.title}\n"
            f"📅 {cls.starts_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Покажи этот QR студентам — они отсканируют в Telegram.\n"
            f"<i>Действителен 2 часа после начала занятия.</i>"
        ),
    )


@router.callback_query(F.data.startswith("adm:roster:"))
async def cb_roster(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    cls_id = int(call.data[len("adm:roster:"):])
    cls = await session.get(Class, cls_id)
    if not cls:
        await call.answer("Не найдено", show_alert=True)
        return

    result = await session.execute(
        select(Booking, User)
        .join(User, Booking.user_id == User.id)
        .where(Booking.class_id == cls_id, Booking.status.in_([
            BookingStatus.CONFIRMED, BookingStatus.ATTENDED
        ]))
    )
    rows = result.all()

    b = InlineKeyboardBuilder()
    for bk, u in rows:
        if bk.status == BookingStatus.CONFIRMED:
            b.button(
                text=f"⬜ {u.full_name[:28]}",
                callback_data=f"adm:mark:{bk.id}:{cls_id}",
            )
        else:
            b.button(
                text=f"✅ {u.full_name[:28]}",
                callback_data=f"adm:unmark:{bk.id}:{cls_id}",
            )
    b.button(text="← К занятию", callback_data=f"adm:cls:{cls_id}")
    b.adjust(1)

    await call.message.edit_text(
        f"✅ <b>Ручная отметка явки</b>\n\n"
        f"🧘 {cls.title} · {cls.starts_at.strftime('%d.%m %H:%M')}\n\n"
        f"Нажми на студента чтобы отметить / снять явку:",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:mark:"))
async def cb_mark_attended(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    parts   = call.data.split(":")
    bk_id   = int(parts[2])
    cls_id  = int(parts[3])
    booking = await session.get(Booking, bk_id)
    if booking:
        booking.status = BookingStatus.ATTENDED
        await session.commit()
    await call.answer("✅ Отмечено")
    # обновляем ростер
    call.data = f"adm:roster:{cls_id}"
    await cb_roster(call, session=session)


@router.callback_query(F.data.startswith("adm:unmark:"))
async def cb_unmark_attended(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    parts   = call.data.split(":")
    bk_id   = int(parts[2])
    cls_id  = int(parts[3])
    booking = await session.get(Booking, bk_id)
    if booking:
        booking.status = BookingStatus.CONFIRMED
        await session.commit()
    await call.answer("↩️ Снято")
    call.data = f"adm:roster:{cls_id}"
    await cb_roster(call, session=session)

@router.callback_query(F.data.startswith("adm:cancel_cls:"))
async def cb_cancel_class(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    cls_id = int(call.data[len("adm:cancel_cls:"):])
    cls = await session.get(Class, cls_id)
    if not cls:
        await call.answer("Не найдено", show_alert=True)
        return
    result = await session.execute(select(Booking).where(Booking.class_id == cls_id, Booking.status == BookingStatus.CONFIRMED))
    bookings = result.scalars().all()
    for bk in bookings:
        bk.status = BookingStatus.CANCELLED
        try:
            await call.bot.send_message(bk.user_id, f"❌ <b>Занятие отменено</b>\n\n{cls.title} — {cls.starts_at.strftime('%d.%m в %H:%M')}\n\nИзвини за неудобство! 🙏")
        except Exception:
            pass
    cls.is_cancelled = True
    await session.commit()
    b = InlineKeyboardBuilder()
    b.button(text="← Расписание", callback_data="adm:schedule")
    b.adjust(1)
    await call.message.edit_text(f"✅ Занятие отменено. Уведомлено: {len(bookings)}", reply_markup=b.as_markup())
    await call.answer()

@router.callback_query(F.data.startswith("adm:clients:"))
async def cb_clients(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    page = int(call.data[len("adm:clients:"):])
    result = await session.execute(select(User).where(User.is_active == True).order_by(User.full_name).offset(page * PAGE_SIZE).limit(PAGE_SIZE + 1))
    users = result.scalars().all()
    has_next = len(users) > PAGE_SIZE
    users = users[:PAGE_SIZE]
    total = await session.scalar(select(func.count(User.id)).where(User.is_active == True)) or 0
    b = InlineKeyboardBuilder()
    for u in users:
        has_sub = await session.scalar(select(func.count(Subscription.id)).where(Subscription.user_id == u.id, Subscription.classes_left > 0)) or 0
        icon = "✅" if has_sub else "⚠️"
        b.button(text=f"{icon} {u.full_name[:26]}", callback_data=f"adm:user:{u.id}")
    if page > 0:
        b.button(text="◀ Пред.", callback_data=f"adm:clients:{page-1}")
    if has_next:
        b.button(text="След. ▶", callback_data=f"adm:clients:{page+1}")
    b.button(text="← Меню", callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text(f"👥 <b>Клиенты</b> — {total} чел.", reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("adm:user:"))
async def cb_user_card(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:user:"):])
    u = await session.get(User, uid)
    if not u:
        await call.answer("Не найдено", show_alert=True)
        return
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == uid, Subscription.classes_left > 0).order_by(Subscription.expires_at))
    missed = await session.scalar(select(func.count(Booking.id)).where(Booking.user_id == uid, Booking.status == BookingStatus.MISSED)) or 0
    total_bk = await session.scalar(select(func.count(Booking.id)).where(Booking.user_id == uid)) or 0
    sub_text = (f"✅ Абонемент: {sub.classes_left} зан." if sub else "⚠️ Абонемента нет")
    b = InlineKeyboardBuilder()
    b.button(text="➕ Начислить занятия", callback_data=f"adm:give:{uid}")
    b.button(text="🔥 Пнуть",            callback_data=f"adm:kick:{uid}")
    b.button(text="📋 История записей",  callback_data=f"adm:bkhistory:{uid}")
    b.button(text="🚫 Заблокировать",    callback_data=f"adm:block:{uid}")
    b.button(text="← Клиенты",         callback_data="adm:clients:0")
    b.adjust(2, 2, 1)
    await call.message.edit_text(
        f"👤 <b>{u.full_name}</b>\n@{u.username or '—'}  ·  <code>{u.id}</code>\n\n{sub_text}\nЗанятий: {total_bk}  ·  пропусков: {missed}",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:give:"))
async def cb_give(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:give:"):])
    b = InlineKeyboardBuilder()
    for n in [1, 2, 4, 8]:
        b.button(text=f"+{n}", callback_data=f"adm:gn:{uid}:{n}")
    b.button(text="← Назад", callback_data=f"adm:user:{uid}")
    b.adjust(4, 1)
    await call.message.edit_text("➕ <b>Начислить занятия</b>\n\nСколько добавить?", reply_markup=b.as_markup())
    await call.answer()

@router.callback_query(F.data.startswith("adm:gn:"))
async def cb_give_n(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    parts = call.data.split(":")
    uid, n = int(parts[2]), int(parts[3])
    u = await session.get(User, uid)
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == uid, Subscription.classes_left > 0))
    if sub:
        sub.classes_left += n
    else:
        sub = Subscription(user_id=uid, sub_type=SubscriptionType.SINGLE, classes_left=n, expires_at=datetime.now() + timedelta(days=90))
        session.add(sub)
    await session.commit()
    try:
        await call.bot.send_message(uid, f"🎁 Тебе начислено <b>{n} занятий</b>!\nЗаписывайся: /schedule")
    except Exception:
        pass
    b = InlineKeyboardBuilder()
    b.button(text="← К клиенту", callback_data=f"adm:user:{uid}")
    b.adjust(1)
    await call.message.edit_text(f"✅ +{n} занятий для <b>{u.full_name}</b>", reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("adm:kick:"))
async def cb_kick(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:kick:"):])
    u = await session.get(User, uid)
    try:
        await call.bot.send_message(uid, f"👋 <b>Привет, {u.full_name.split()[0]}!</b>\n\nДавно тебя не было — скучаем! 🧘\nРасписание: /schedule")
        await call.answer("✅ Пинок отправлен!", show_alert=True)
    except Exception:
        await call.answer("❌ Клиент заблокировал бота", show_alert=True)

@router.callback_query(F.data.startswith("adm:block:"))
async def cb_block(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:block:"):])
    u = await session.get(User, uid)
    b = InlineKeyboardBuilder()
    b.button(text="🚫 Да, заблокировать", callback_data=f"adm:block_confirm:{uid}")
    b.button(text="← Назад", callback_data=f"adm:user:{uid}")
    b.adjust(1)
    await call.message.edit_text(
        f"Заблокировать <b>{u.full_name}</b>?\n\nПользователь потеряет доступ к боту.",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:block_confirm:"))
async def cb_block_confirm(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:block_confirm:"):])
    u = await session.get(User, uid)
    u.is_active = False
    await session.commit()
    b = InlineKeyboardBuilder()
    b.button(text="← К списку клиентов", callback_data="adm:clients:0")
    b.adjust(1)
    await call.message.edit_text(f"🚫 <b>{u.full_name}</b> заблокирован.", reply_markup=b.as_markup())
    await call.answer()

@router.callback_query(F.data.startswith("adm:bkhistory:"))
async def cb_bk_history(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    uid = int(call.data[len("adm:bkhistory:"):])
    result = await session.execute(select(Booking, Class).join(Class, Booking.class_id == Class.id).where(Booking.user_id == uid).order_by(Class.starts_at.desc()).limit(10))
    rows = result.all()
    STATUS = {BookingStatus.CONFIRMED: "✅", BookingStatus.CANCELLED: "❌", BookingStatus.MISSED: "😔", BookingStatus.ATTENDED: "✔️"}
    lines = [f"{STATUS.get(bk.status,'?')} {cls.starts_at.strftime('%d.%m %H:%M')} {cls.title[:20]}" for bk, cls in rows] or ["Записей нет"]
    b = InlineKeyboardBuilder()
    b.button(text="← Назад", callback_data=f"adm:user:{uid}")
    b.adjust(1)
    await call.message.edit_text("<b>История (последние 10):</b>\n\n" + "\n".join(lines), reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data == "adm:payments")
async def cb_payments(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    month_total = await session.scalar(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.SUCCEEDED, Payment.paid_at >= month_start)) or 0
    result = await session.execute(select(Payment, User).join(User, Payment.user_id == User.id).where(Payment.status == PaymentStatus.SUCCEEDED).order_by(Payment.paid_at.desc()).limit(15))
    rows = result.all()
    lines = [f"💰 <b>Платежи</b>  ·  месяц: <b>{month_total:,} сум</b>\n"]
    for pay, u in rows:
        dt = pay.paid_at.strftime("%d.%m %H:%M") if pay.paid_at else "—"
        lines.append(f"{dt}  {u.full_name[:20]}  <b>{pay.amount:,} сум</b>")
    b = InlineKeyboardBuilder()
    b.button(text="← Меню", callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text("\n".join(lines), reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data == "adm:stats")
async def cb_stats(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    total_users = await session.scalar(select(func.count(User.id)).where(User.is_active == True)) or 0
    total_cls = await session.scalar(select(func.count(Class.id)).where(Class.is_cancelled == False)) or 0
    total_bk = await session.scalar(select(func.count(Booking.id))) or 0
    missed = await session.scalar(select(func.count(Booking.id)).where(Booking.status == BookingStatus.MISSED)) or 0
    active_subs = await session.scalar(select(func.count(Subscription.id)).where(Subscription.classes_left > 0)) or 0
    total_income = await session.scalar(select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.SUCCEEDED)) or 0
    miss_pct = round(missed / total_bk * 100) if total_bk else 0
    b = InlineKeyboardBuilder()
    b.button(text="← Меню", callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text(
        f"📊 <b>Статистика</b>\n\n👥 Клиентов: {total_users}\n📋 Абонементов: {active_subs}\n📅 Занятий: {total_cls}\n✅ Записей: {total_bk}\n😔 Пропусков: {missed} ({miss_pct}%)\n💰 Доход: <b>{total_income:,} сум</b>",
        reply_markup=b.as_markup(),
    )
    await call.answer()


# ═══ НАСТРОЙКИ ═══

SETTINGS_LABELS = {
    "studio_name":      "🏠 Название студии",
    "studio_phone":     "📞 Телефон",
    "studio_address":   "📍 Адрес",
    "studio_instagram": "📸 Instagram",
    "studio_schedule":  "🕐 Часы работы",
    "trainer_telegram": "🧘 Telegram тренера (@username)",
    "locations":        "📍 Студии/локации (через |)",
    "trainers":         "👤 Тренеры (через |)",
    "class_templates":  "📋 Шаблоны занятий (через |)",
    "price_single":     "💰 Цена разовое (сум)",
    "price_pack_4":     "💰 Цена 4 занятия (сум)",
    "price_pack_8":     "💰 Цена 8 занятий (сум)",
}

@router.callback_query(F.data == "adm:settings")
async def cb_settings(call: CallbackQuery, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    from db.queries import get_all_settings
    s = await get_all_settings(session)
    b = InlineKeyboardBuilder()
    for key, label in SETTINGS_LABELS.items():
        val = s.get(key, "—")
        if len(val) > 20:
            val = val[:20] + "..."
        b.button(text=f"{label}: {val}", callback_data=f"adm:setedit:{key}")
    b.button(text="← Меню", callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text("⚙️ <b>Настройки студии</b>\n\nНажми на параметр чтобы изменить:", reply_markup=b.as_markup())
    await call.answer()

@router.callback_query(F.data.startswith("adm:setedit:"))
async def cb_settings_edit(call: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs):
    if not await check_admin(call):
        return
    key = call.data[len("adm:setedit:"):]
    label = SETTINGS_LABELS.get(key, key)
    from db.queries import get_setting
    current = await get_setting(session, key)
    await state.update_data(edit_key=key)
    await state.set_state(SettingsFSM.edit_value)
    hints = ""
    if key == "locations":
        hints = "\n\n<i>Пример: Мои занятия|Студия на Ленина|Студия на Маркса</i>"
    elif key == "trainers":
        hints = "\n\n<i>Пример: Юлия Николаева|Анна Громова</i>"
    elif key == "class_templates":
        hints = "\n\n<i>Пример: Пилатес базовый|Пилатес продвинутый|Стретчинг</i>"
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="adm:settings")
    b.adjust(1)
    await call.message.edit_text(
        f"⚙️ <b>{label}</b>\n\nТекущее значение:\n<code>{current}</code>\n\nВведи новое значение:{hints}",
        reply_markup=b.as_markup()
    )
    await call.answer()

@router.message(SettingsFSM.edit_value)
async def msg_settings_value(message: Message, state: FSMContext, session: AsyncSession, **kwargs):
    if not await check_admin(message):
        return
    data = await state.get_data()
    key = data.get("edit_key")
    value = message.text.strip()
    await state.clear()
    from db.queries import set_setting
    await set_setting(session, key, value)
    label = SETTINGS_LABELS.get(key, key)
    b = InlineKeyboardBuilder()
    b.button(text="← Настройки", callback_data="adm:settings")
    b.button(text="← Меню",             callback_data="adm:main")
    b.adjust(1)
    await message.answer(f"✅ <b>{label}</b> обновлено!\n\nНовое значение: <code>{value}</code>", reply_markup=b.as_markup())

@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast_start(call: CallbackQuery, state: FSMContext, **kwargs):
    if not await check_admin(call):
        return
    await state.set_state(BroadcastFSM.text)
    await call.message.edit_text("📣 <b>Рассылка</b>\n\nВведи текст:")
    await call.answer()

@router.message(BroadcastFSM.text)
async def msg_broadcast_text(message: Message, state: FSMContext, **kwargs):
    await state.update_data(text=message.text)
    await state.set_state(BroadcastFSM.confirm)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить всем", callback_data="adm:bcast_go")
    b.button(text="❌ Отмена",         callback_data="adm:main")
    b.adjust(1)
    await message.answer(f"📣 <b>Предпросмотр:</b>\n\n{message.text}\n\nОтправить всем?", reply_markup=b.as_markup())

@router.callback_query(F.data == "adm:bcast_go", BroadcastFSM.confirm)
async def cb_broadcast_go(call: CallbackQuery, session: AsyncSession, state: FSMContext, **kwargs):
    if not await check_admin(call):
        return
    data = await state.get_data()
    await state.clear()
    text = data.get("text", "")
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
    b.button(text="← Меню", callback_data="adm:main")
    b.adjust(1)
    await call.message.edit_text(f"📣 <b>Готово!</b>\n\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}", reply_markup=b.as_markup())
    await call.answer()
