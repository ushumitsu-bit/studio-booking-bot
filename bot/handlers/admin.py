"""
Роутер администратора.
Доступен только пользователям из ADMIN_IDS.

Команды:
  /admin         — меню администратора
  /addclass      — добавить занятие (FSM)
  /clients       — список клиентов с долгами
  /broadcast     — рассылка всем клиентам
"""

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.engine import AsyncSessionFactory
from db.models import Class, Subscription, User
from db.queries import create_class, get_all_active_users

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


def admin_only(handler):
    async def wrapper(event: Message | CallbackQuery, *args, **kwargs):
        uid = event.from_user.id
        if not is_admin(uid):
            if isinstance(event, Message):
                await event.answer("⛔ Нет доступа")
            else:
                await event.answer("⛔ Нет доступа", show_alert=True)
            return
        return await handler(event, *args, **kwargs)
    return wrapper


# ─────────────────────── FSM для занятия ─────────────────────────

class AddClassFSM(StatesGroup):
    title     = State()
    trainer   = State()
    date_time = State()
    max_spots = State()


# ─────────────────────── /admin ──────────────────────────────────

@router.message(Command("admin"))
@admin_only
async def admin_menu(message: Message):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить занятие", callback_data="admin_addclass"))
    builder.row(InlineKeyboardButton(text="👥 Клиенты с долгами", callback_data="admin_debtors"))
    builder.row(InlineKeyboardButton(text="📣 Рассылка", callback_data="admin_broadcast"))
    await message.answer(
        "🔧 <b>Панель администратора</b>",
        reply_markup=builder.as_markup(),
    )


# ─────────────────────── Добавить занятие ────────────────────────

@router.callback_query(F.data == "admin_addclass")
@admin_only
async def admin_addclass_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddClassFSM.title)
    await call.message.edit_text(
        "📝 Введи название занятия:\n\n<i>Например: Пилатес для начинающих</i>"
    )


@router.message(AddClassFSM.title)
async def addclass_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddClassFSM.trainer)
    await message.answer("👩‍🏫 Введи имя тренера:")


@router.message(AddClassFSM.trainer)
async def addclass_trainer(message: Message, state: FSMContext):
    await state.update_data(trainer=message.text.strip())
    await state.set_state(AddClassFSM.date_time)
    await message.answer(
        "📅 Введи дату и время в формате:\n<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n\n"
        "<i>Например: 07.04.2025 09:00</i>"
    )


@router.message(AddClassFSM.date_time)
async def addclass_datetime(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Попробуй ещё раз: ДД.ММ.ГГГГ ЧЧ:ММ")
        return
    await state.update_data(starts_at=dt)
    await state.set_state(AddClassFSM.max_spots)
    await message.answer("👥 Сколько мест? (введи число, например 8):")


@router.message(AddClassFSM.max_spots)
async def addclass_spots(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text.strip().isdigit():
        await message.answer("❌ Введи число")
        return

    data = await state.get_data()
    await state.clear()

    cls = await create_class(
        session,
        title=data["title"],
        trainer=data["trainer"],
        starts_at=data["starts_at"],
        max_spots=int(message.text.strip()),
    )
    await message.answer(
        f"✅ <b>Занятие добавлено!</b>\n\n"
        f"🧘 {cls.title}\n"
        f"📅 {cls.starts_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"👩‍🏫 {cls.trainer}\n"
        f"👥 {cls.max_spots} мест"
    )


# ─────────────────────── Клиенты с долгами ───────────────────────

@router.callback_query(F.data == "admin_debtors")
@admin_only
async def admin_debtors(call: CallbackQuery, session: AsyncSession):
    # Клиенты без активного абонемента с хотя бы 1 подтверждённой записью
    result = await session.execute(
        select(User).where(User.is_active == True)
    )
    users = result.scalars().all()

    lines = ["👥 <b>Клиенты без активного абонемента:</b>\n"]
    count = 0
    for user in users:
        subs = [s for s in user.subscriptions if s.classes_left > 0]
        if not subs:
            name = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
            lines.append(f"• {name} (@{user.username or '—'})")
            count += 1

    if count == 0:
        lines = ["✅ Все клиенты с активными абонементами!"]

    await call.message.edit_text(
        "\n".join(lines),
        disable_web_page_preview=True,
    )


# ─────────────────────── Рассылка ────────────────────────────────

class BroadcastFSM(StatesGroup):
    text = State()


@router.callback_query(F.data == "admin_broadcast")
@admin_only
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastFSM.text)
    await call.message.edit_text(
        "📣 Введи текст для рассылки всем клиентам.\n\n"
        "Можно использовать <b>жирный</b> и <i>курсив</i>."
    )


@router.message(BroadcastFSM.text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    await state.clear()
    text = message.text

    async with AsyncSessionFactory() as session:
        users = await get_all_active_users(session)

    sent = 0
    failed = 0
    for user in users:
        try:
            await message.bot.send_message(user.id, text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"📣 Рассылка завершена!\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибки: {failed}"
    )
