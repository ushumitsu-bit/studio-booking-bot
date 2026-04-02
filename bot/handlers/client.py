"""
Основной роутер для клиентов.
Команды: /start, /schedule, /book, /mybookings, /mysub, /pay
"""

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import (
    back_to_menu,
    classes_keyboard,
    confirm_booking_keyboard,
    main_menu,
    my_bookings_keyboard,
    payment_plans_keyboard,
)
from db.models import User
from db.queries import (
    cancel_booking,
    create_booking,
    decrement_subscription,
    get_active_subscription,
    get_booking,
    get_class_by_id,
    get_upcoming_classes,
    get_user_upcoming_bookings,
)

router = Router()


# ─────────────────────── /start ──────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User):
    await message.answer(
        f"Привет, <b>{db_user.full_name}</b>! 🧘\n\n"
        f"Я помогу тебе записаться на пилатес, посмотреть расписание "
        f"и оплатить абонемент прямо здесь.\n\n"
        f"Что хочешь сделать?",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery, db_user: User):
    await call.message.edit_text(
        f"Главное меню 🏠\n\nЧто хочешь сделать, <b>{db_user.full_name}</b>?",
        reply_markup=main_menu(),
    )


# ─────────────────────── Расписание ──────────────────────────────

@router.message(Command("schedule"))
@router.callback_query(F.data == "schedule")
async def show_schedule(event: Message | CallbackQuery, session: AsyncSession):
    classes = await get_upcoming_classes(session, days=7)

    if not classes:
        text = "📅 На ближайшие 7 дней занятий нет.\n\nСкоро добавим расписание!"
    else:
        lines = ["📅 <b>Расписание на неделю:</b>\n"]
        current_day = None
        for cls in classes:
            day = cls.starts_at.strftime("%A %d.%m")
            days_ru = {
                "Monday": "Понедельник", "Tuesday": "Вторник",
                "Wednesday": "Среда", "Thursday": "Четверг",
                "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье",
            }
            day_name = cls.starts_at.strftime("%A")
            day_label = f"{days_ru.get(day_name, day_name)}, {cls.starts_at.strftime('%d.%m')}"

            if current_day != day_label:
                lines.append(f"\n<b>{day_label}</b>")
                current_day = day_label

            spots = cls.free_spots
            spot_icon = "✅" if spots > 2 else ("⚠️" if spots > 0 else "❌")
            lines.append(
                f"  {cls.starts_at.strftime('%H:%M')} · {cls.title} "
                f"({cls.trainer}) {spot_icon} {spots}/{cls.max_spots}"
            )

        text = "\n".join(lines)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=back_to_menu())
    else:
        await event.answer(text, reply_markup=back_to_menu())


# ─────────────────────── Запись ──────────────────────────────────

@router.message(Command("book"))
@router.callback_query(F.data == "book")
async def show_booking_list(event: Message | CallbackQuery, session: AsyncSession):
    classes = await get_upcoming_classes(session, days=7)
    available = [c for c in classes if c.free_spots > 0]

    if not available:
        text = "К сожалению, свободных мест нет. Загляни позже 😔"
        kb = back_to_menu()
    else:
        text = "✏️ <b>Выбери занятие для записи:</b>"
        kb = classes_keyboard(available)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)


@router.callback_query(F.data == "full")
async def spot_full(call: CallbackQuery):
    await call.answer("Мест нет 😔 Попробуй другое занятие", show_alert=True)


@router.callback_query(F.data.startswith("book_"))
async def confirm_booking_prompt(call: CallbackQuery, session: AsyncSession, db_user: User):
    class_id = int(call.data.split("_")[1])
    cls = await get_class_by_id(session, class_id)
    if not cls:
        await call.answer("Занятие не найдено", show_alert=True)
        return

    # Проверяем, нет ли уже записи
    existing = await get_booking(session, db_user.id, class_id)
    if existing and existing.status.value == "confirmed":
        await call.answer("Ты уже записана на это занятие ✅", show_alert=True)
        return

    # Проверяем абонемент
    sub = await get_active_subscription(session, db_user.id)
    sub_info = f"✅ Абонемент: {sub.classes_left} занятий" if sub else "⚠️ <b>Активного абонемента нет.</b> Запись без оплаты — нужно будет оплатить на месте или через бота."

    time_str = cls.starts_at.strftime("%d.%m.%Y в %H:%M")
    await call.message.edit_text(
        f"📌 <b>Подтверди запись:</b>\n\n"
        f"🧘 {cls.title}\n"
        f"📅 {time_str}\n"
        f"👩‍🏫 Тренер: {cls.trainer}\n"
        f"👥 Мест: {cls.free_spots}/{cls.max_spots}\n\n"
        f"{sub_info}",
        reply_markup=confirm_booking_keyboard(class_id),
    )


@router.callback_query(F.data.startswith("confirm_book_"))
async def do_booking(call: CallbackQuery, session: AsyncSession, db_user: User):
    class_id = int(call.data.split("_")[2])
    cls = await get_class_by_id(session, class_id)
    if not cls or cls.free_spots <= 0:
        await call.answer("Мест уже нет 😔", show_alert=True)
        return

    await create_booking(session, db_user.id, class_id)
    await decrement_subscription(session, db_user.id)

    time_str = cls.starts_at.strftime("%d.%m в %H:%M")
    await call.message.edit_text(
        f"🎉 <b>Готово! Ты записана.</b>\n\n"
        f"🧘 {cls.title}\n"
        f"📅 {time_str}\n\n"
        f"Напомню за 24 часа и за 2 часа до занятия ⏰",
        reply_markup=back_to_menu(),
    )


# ─────────────────────── Мои записи ──────────────────────────────

@router.message(Command("mybookings"))
@router.callback_query(F.data == "my_bookings")
async def my_bookings(event: Message | CallbackQuery, session: AsyncSession, db_user: User):
    bookings = await get_user_upcoming_bookings(session, db_user.id)

    if not bookings:
        text = "У тебя нет предстоящих занятий.\n\nЗапишись: /book"
        kb = back_to_menu()
    else:
        lines = ["🗓 <b>Твои ближайшие занятия:</b>\n"]
        for b in bookings:
            lines.append(f"• {b.cls.starts_at.strftime('%d.%m %H:%M')} — {b.cls.title}")
        text = "\n".join(lines) + "\n\nНажми на занятие чтобы отменить:"
        kb = my_bookings_keyboard(bookings)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking_cb(call: CallbackQuery, session: AsyncSession):
    booking_id = int(call.data.split("_")[2])
    await cancel_booking(session, booking_id)
    await call.message.edit_text(
        "✅ Запись отменена. Место освобождено.\n\nДо встречи на следующем занятии! 💛",
        reply_markup=back_to_menu(),
    )


# ─────────────────────── Абонемент ───────────────────────────────

@router.message(Command("mysub"))
@router.callback_query(F.data == "my_sub")
async def my_subscription(event: Message | CallbackQuery, session: AsyncSession, db_user: User):
    sub = await get_active_subscription(session, db_user.id)

    if not sub:
        text = (
            "📊 <b>Активного абонемента нет.</b>\n\n"
            "Купи абонемент прямо здесь — это быстро и безопасно 👇"
        )
    else:
        expires = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "—"
        text = (
            f"📊 <b>Твой абонемент:</b>\n\n"
            f"Осталось занятий: <b>{sub.classes_left}</b>\n"
            f"Действует до: <b>{expires}</b>"
        )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=back_to_menu())
    else:
        await event.answer(text, reply_markup=back_to_menu())
