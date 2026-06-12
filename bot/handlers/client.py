"""
Клиентские хэндлеры — /start, расписание, запись, мои занятия, абонемент, профиль, отзыв.
"""

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, Message,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.translations import (
    t, gender_label, level_label, pref_label, lang_label,
)
from config import settings
from db.models import (
    Booking, BookingStatus, Class, Subscription, User, UserLanguage,
)
from db.queries import (
    add_to_waitlist,
    cancel_booking,
    create_booking,
    decrement_subscription,
    get_active_subscription,
    get_booking,
    get_class_by_id,
    get_upcoming_classes,
    get_user_upcoming_bookings,
    get_waitlist_entry,
    has_feedback,
    save_feedback,
    SUBSCRIPTION_CLASSES,
)

router = Router()

DAYS_RU = {
    "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
    "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье",
}
DAYS_SHORT = {
    "Monday": "Пн", "Tuesday": "Вт", "Wednesday": "Ср",
    "Thursday": "Чт", "Friday": "Пт", "Saturday": "Сб", "Sunday": "Вс",
}


def _lang(db_user: User) -> str:
    if db_user.language:
        return db_user.language.value
    return "ru"


def _first_name(user: User) -> str:
    if user.full_name:
        return user.full_name.split()[0]
    return user.username or "друг"


def _webapp_kb(lang: str = "ru"):
    from config import settings as cfg
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(
            text=t("btn_open_app", lang, studio=cfg.STUDIO_NAME),
            web_app=WebAppInfo(url=f"{cfg.WEBHOOK_HOST}/miniapp/"),
        )]],
        resize_keyboard=True,
    )


def _main_menu_kb(lang: str = "ru"):
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_schedule",    lang), callback_data="schedule:0")
    b.button(text=t("btn_my_bookings", lang), callback_data="my_bookings")
    b.button(text=t("btn_my_sub",      lang), callback_data="my_sub")
    b.button(text=t("btn_individual",  lang), callback_data="individual")
    b.button(text=t("btn_profile",     lang), callback_data="profile")
    b.button(text=t("btn_contacts",    lang), callback_data="contacts")
    b.adjust(1)
    return b.as_markup()


# ─────────────────────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, state: FSMContext, **kwargs):
    if not db_user.onboarding_done:
        from bot.handlers.onboarding import start_onboarding
        await start_onboarding(message, state)
        return

    lang = _lang(db_user)
    name = _first_name(db_user)
    text = t("welcome_back", lang, name=name, studio=settings.STUDIO_NAME)
    await message.answer(text, reply_markup=_main_menu_kb(lang))


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery, db_user: User, **kwargs):
    lang = _lang(db_user)
    name = _first_name(db_user)
    await call.message.edit_text(
        t("main_menu_title", lang, name=name),
        reply_markup=_main_menu_kb(lang),
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────
# РАСПИСАНИЕ
# ─────────────────────────────────────────────────────────────

@router.message(Command("schedule"))
@router.callback_query(F.data.startswith("schedule:"))
async def show_schedule(event, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)

    if isinstance(event, CallbackQuery):
        day_offset = int(event.data.split(":")[1])
    else:
        day_offset = 0

    classes = await get_upcoming_classes(session, days=14)

    if not classes:
        text = t("no_classes", lang)
        b = InlineKeyboardBuilder()
        b.button(text=t("btn_menu", lang), callback_data="menu")
        b.adjust(1)
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=b.as_markup())
            await event.answer()
        else:
            await event.answer(text, reply_markup=b.as_markup())
        return

    days: dict[str, list[Class]] = {}
    for cls in classes:
        day_key = cls.starts_at.strftime("%Y-%m-%d")
        days.setdefault(day_key, []).append(cls)

    day_keys = sorted(days.keys())
    total_days = len(day_keys)
    day_offset = max(0, min(day_offset, total_days - 1))
    current_day_key = day_keys[day_offset]
    current_classes = days[current_day_key]
    current_dt = datetime.strptime(current_day_key, "%Y-%m-%d")

    day_name = DAYS_RU.get(current_dt.strftime("%A"), current_dt.strftime("%A"))
    day_str  = current_dt.strftime("%d.%m")
    is_today = current_dt.date() == datetime.now().date()
    today_label = t("today_label", lang) if is_today else ""

    client_bookings = await get_user_upcoming_bookings(session, db_user.id)
    booked_class_ids = {b.class_id for b in client_bookings}

    lines = [f"📅 <b>{day_name}, {day_str}{today_label}</b>\n"]

    for cls in sorted(current_classes, key=lambda c: c.starts_at):
        confirmed = [b for b in cls.bookings if b.status == BookingStatus.CONFIRMED]
        free = cls.max_spots - len(confirmed)

        if free > 2:
            spots_icon = "🟢"
            spots_text = t("spots_count", lang, n=free)
        elif free > 0:
            spots_icon = "🟡"
            spots_text = t("spots_count", lang, n=free)
        else:
            spots_icon = "🔴"
            spots_text = t("spots_none", lang)

        is_booked = cls.id in booked_class_ids
        booked_mark = t("you_booked", lang) if is_booked else ""

        zoom_line = ""
        if cls.zoom_link:
            zoom_line = f"\n   " + t("zoom_link_label", lang, link=cls.zoom_link)

        lines.append(
            f"{spots_icon} <b>{cls.starts_at.strftime('%H:%M')}</b> — {cls.title}\n"
            f"   👤 {cls.trainer}  ·  {spots_text}{booked_mark}{zoom_line}"
        )

    text = "\n\n".join(lines)

    b = InlineKeyboardBuilder()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_offset = next((i for i, k in enumerate(day_keys) if k == today_str), None)

    if day_offset > 0:
        prev_dt  = datetime.strptime(day_keys[day_offset - 1], "%Y-%m-%d")
        prev_day = DAYS_SHORT.get(prev_dt.strftime("%A"), "")
        b.button(text=f"◀ {prev_day} {prev_dt.strftime('%d.%m')}", callback_data=f"schedule:{day_offset - 1}")
    if day_offset < total_days - 1:
        next_dt  = datetime.strptime(day_keys[day_offset + 1], "%Y-%m-%d")
        next_day = DAYS_SHORT.get(next_dt.strftime("%A"), "")
        b.button(text=f"{next_day} {next_dt.strftime('%d.%m')} ▶", callback_data=f"schedule:{day_offset + 1}")

    b.adjust(2)

    if today_offset is not None and today_offset != day_offset:
        b.button(text=t("btn_today", lang), callback_data=f"schedule:{today_offset}")
        b.adjust(1)

    for cls in sorted(current_classes, key=lambda c: c.starts_at):
        confirmed = [bk for bk in cls.bookings if bk.status == BookingStatus.CONFIRMED]
        free = cls.max_spots - len(confirmed)
        is_booked = cls.id in booked_class_ids

        if is_booked:
            b.button(text=f"✅ Записана {cls.starts_at.strftime('%H:%M')} — отменить", callback_data=f"cancel_from_schedule:{cls.id}")
        elif free > 0:
            b.button(text=f"🟢 Записаться {cls.starts_at.strftime('%H:%M')}", callback_data=f"book_{cls.id}")
        else:
            b.button(text=f"🔴 {cls.starts_at.strftime('%H:%M')} — {t('spots_none', lang)}", callback_data=f"waitlist_prompt_{cls.id}")
        b.adjust(1)

    b.button(text=t("btn_menu", lang), callback_data="menu")
    b.adjust(1)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=b.as_markup())
        await event.answer()
    else:
        await event.answer(text, reply_markup=b.as_markup())


# ─────────────────────────────────────────────────────────────
# ЛИСТ ОЖИДАНИЯ
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("waitlist_prompt_"))
async def waitlist_prompt(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    class_id = int(call.data.split("_")[2])
    cls = await get_class_by_id(session, class_id)
    if not cls:
        await call.answer("Не найдено", show_alert=True)
        return

    existing = await get_waitlist_entry(session, db_user.id, class_id)
    if existing:
        await call.answer(t("waitlist_already", lang), show_alert=True)
        return

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_join_waitlist", lang), callback_data=f"waitlist_join_{class_id}")
    b.button(text=t("btn_menu", lang), callback_data="menu")
    b.adjust(1)

    await call.message.edit_text(
        t("waitlist_prompt", lang) + f"\n\n🧘 <b>{cls.title}</b>\n📅 {cls.starts_at.strftime('%d.%m.%Y в %H:%M')}",
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("waitlist_join_"))
async def waitlist_join(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    class_id = int(call.data.split("_")[2])

    existing = await get_waitlist_entry(session, db_user.id, class_id)
    if existing:
        await call.answer(t("waitlist_already", lang), show_alert=True)
        return

    await add_to_waitlist(session, db_user.id, class_id)

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_schedule", lang), callback_data="schedule:0")
    b.button(text=t("btn_menu",     lang), callback_data="menu")
    b.adjust(1)

    await call.message.edit_text(t("waitlist_joined", lang), reply_markup=b.as_markup())
    await call.answer("✅")


# ─────────────────────────────────────────────────────────────
# ЗАПИСЬ
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "full")
async def spot_full(call: CallbackQuery, db_user: User, **kwargs):
    lang = _lang(db_user)
    await call.answer(t("no_spots_alert", lang), show_alert=True)


@router.callback_query(F.data.startswith("book_"))
async def confirm_booking_prompt(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    class_id = int(call.data.split("_")[1])
    cls = await get_class_by_id(session, class_id)
    if not cls:
        await call.answer("Занятие не найдено", show_alert=True)
        return

    existing = await get_booking(session, db_user.id, class_id)
    if existing and existing.status == BookingStatus.CONFIRMED:
        await call.answer(t("already_booked", lang), show_alert=True)
        return

    sub = await get_active_subscription(session, db_user.id)
    sub_info = (
        t("sub_ok", lang, n=sub.classes_left)
        if sub
        else t("sub_none", lang)
    )

    spots = cls.free_spots
    spots_icon = "🟢" if spots > 2 else "🟡" if spots > 0 else "🔴"

    b = InlineKeyboardBuilder()
    if sub:
        b.button(text=t("btn_book_confirm", lang), callback_data=f"confirm_book_{class_id}")
    else:
        b.button(text=t("btn_buy_sub", lang), callback_data="pay")
    b.button(text=t("btn_schedule", lang), callback_data="schedule:0")
    b.adjust(1)

    await call.message.edit_text(
        t("confirm_booking", lang,
          title=cls.title,
          dt=cls.starts_at.strftime("%d.%m.%Y в %H:%M"),
          trainer=cls.trainer,
          spots_icon=spots_icon,
          spots=spots,
          max=cls.max_spots,
          sub_info=sub_info),
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("confirm_book_"))
async def do_booking(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    class_id = int(call.data.split("_")[2])
    cls = await get_class_by_id(session, class_id)
    if not cls or cls.free_spots <= 0:
        await call.answer(t("no_spots_full", lang), show_alert=True)
        return

    await create_booking(session, db_user.id, class_id)
    await decrement_subscription(session, db_user.id)

    # Уведомить админов если записался парень
    from db.models import Gender
    if db_user.gender == Gender.MALE:
        for admin_id in settings.ADMIN_IDS:
            try:
                await call.bot.send_message(
                    admin_id,
                    f"🕺 <b>Парень записался!</b>\n\n"
                    f"👤 {db_user.full_name} (@{db_user.username or '—'})\n"
                    f"🧘 {cls.title}\n"
                    f"📅 {cls.starts_at.strftime('%d.%m.%Y в %H:%M')}",
                )
            except Exception:
                pass

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_my_bookings", lang), callback_data="my_bookings")
    b.button(text=t("btn_menu",        lang), callback_data="menu")
    b.adjust(1)

    await call.message.edit_text(
        t("booked_ok", lang,
          title=cls.title,
          dt=cls.starts_at.strftime("%d.%m.%Y в %H:%M"),
          trainer=cls.trainer),
        reply_markup=b.as_markup(),
    )
    await call.answer("✅")


@router.callback_query(F.data.startswith("cancel_from_schedule:"))
async def cancel_from_schedule(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    class_id = int(call.data.split(":")[1])
    existing = await get_booking(session, db_user.id, class_id)
    if not existing:
        await call.answer("Запись не найдена", show_alert=True)
        return
    cls = await get_class_by_id(session, class_id)
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_yes_cancel", lang), callback_data=f"confirm_cancel_{existing.id}")
    b.button(text="← Назад", callback_data="schedule:0")
    b.adjust(1)
    await call.message.edit_text(
        t("cancel_confirm_prompt", lang,
          title=cls.title,
          dt=cls.starts_at.strftime("%d.%m.%Y в %H:%M"),
          trainer=cls.trainer),
        reply_markup=b.as_markup(),
    )
    await call.answer()


# ─────────────────────────────────────────────────────────────
# МОИ ЗАПИСИ
# ─────────────────────────────────────────────────────────────

@router.message(Command("mybookings"))
@router.callback_query(F.data == "my_bookings")
async def my_bookings(event, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    bookings = await get_user_upcoming_bookings(session, db_user.id)

    b = InlineKeyboardBuilder()
    if not bookings:
        text = t("no_bookings", lang)
        b.button(text=t("btn_schedule",    lang), callback_data="schedule:0")
        b.button(text=t("btn_menu",        lang), callback_data="menu")
        b.adjust(1)
    else:
        lines = [t("my_bookings_title", lang)]
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
        b.button(text=t("btn_menu", lang), callback_data="menu")
        b.adjust(1)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=b.as_markup())
        await event.answer()
    else:
        await event.answer(text, reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking_cb(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    booking_id = int(call.data.split("_")[2])
    from db.models import Booking as BookingModel
    bk = await session.get(BookingModel, booking_id)
    if not bk:
        await call.answer("Запись не найдена", show_alert=True)
        return
    cls = await get_class_by_id(session, bk.class_id)
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_yes_cancel", lang), callback_data=f"confirm_cancel_{booking_id}")
    b.button(text="← Назад", callback_data="my_bookings")
    b.adjust(1)
    await call.message.edit_text(
        t("cancel_confirm_prompt", lang,
          title=cls.title,
          dt=cls.starts_at.strftime("%d.%m.%Y в %H:%M"),
          trainer=cls.trainer),
        reply_markup=b.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("confirm_cancel_"))
async def confirm_cancel_cb(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    booking_id = int(call.data.split("_")[2])
    from db.models import Booking as _Booking
    bk = await session.get(_Booking, booking_id)
    if not bk or bk.user_id != db_user.id:
        await call.answer("Запись не найдена", show_alert=True)
        return

    # Уведомить первого в листе ожидания
    from db.queries import get_next_waitlist, mark_waitlist_notified
    cls = await get_class_by_id(session, bk.class_id)
    await cancel_booking(session, booking_id)

    next_wait = await get_next_waitlist(session, bk.class_id)
    if next_wait:
        await mark_waitlist_notified(session, next_wait.id)
        wait_lang = next_wait.user.language.value if next_wait.user.language else "ru"
        b_notify = InlineKeyboardBuilder()
        b_notify.button(
            text=t("btn_book_now", wait_lang),
            callback_data=f"book_{bk.class_id}",
        )
        try:
            await call.bot.send_message(
                next_wait.user_id,
                t("waitlist_notify", wait_lang,
                  title=cls.title,
                  dt=cls.starts_at.strftime("%d.%m.%Y в %H:%M")),
                reply_markup=b_notify.as_markup(),
            )
        except Exception:
            pass

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_schedule", lang), callback_data="schedule:0")
    b.button(text=t("btn_menu",     lang), callback_data="menu")
    b.adjust(1)
    await call.message.edit_text(t("cancel_done", lang), reply_markup=b.as_markup())
    await call.answer()


# ─────────────────────────────────────────────────────────────
# МОЙ АБОНЕМЕНТ
# ─────────────────────────────────────────────────────────────

class FreezeFSM(StatesGroup):
    days = State()


@router.message(Command("mysub"))
@router.callback_query(F.data == "my_sub")
async def my_subscription(event, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    sub = await get_active_subscription(session, db_user.id)

    b = InlineKeyboardBuilder()
    if not sub:
        # Проверить замороженный абонемент
        from sqlalchemy import select as _s
        frozen = await session.scalar(
            _s(Subscription).where(
                Subscription.user_id == db_user.id,
                Subscription.is_frozen == True,
                Subscription.classes_left > 0,
            )
        )
        if frozen:
            date_str = frozen.frozen_until.strftime("%d.%m.%Y") if frozen.frozen_until else "—"
            text = t("sub_frozen", lang, date=date_str)
        else:
            text = t("no_sub", lang)
            b.button(text=t("btn_buy_sub", lang), callback_data="pay")
    else:
        expires = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "—"
        total = SUBSCRIPTION_CLASSES.get(sub.sub_type, sub.classes_left)
        used = total - sub.classes_left
        bar = "🟩" * sub.classes_left + "⬜" * used

        text = t("sub_status", lang, bar=bar, left=sub.classes_left, expires=expires)
        b.button(text=t("btn_schedule",  lang), callback_data="schedule:0")
        b.button(text=t("btn_buy_more",  lang), callback_data="pay")
        b.button(text=t("btn_freeze",    lang), callback_data=f"freeze_prompt_{sub.id}")

    b.button(text=t("btn_menu", lang), callback_data="menu")
    b.adjust(1)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=b.as_markup())
        await event.answer()
    else:
        await event.answer(text, reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("freeze_prompt_"))
async def freeze_prompt(call: CallbackQuery, state: FSMContext, db_user: User, **kwargs):
    lang = _lang(db_user)
    sub_id = int(call.data.split("_")[2])
    await state.update_data(sub_id=sub_id)
    await state.set_state(FreezeFSM.days)

    b = InlineKeyboardBuilder()
    for n in [7, 14, 30]:
        b.button(text=f"{n} дн.", callback_data=f"freeze_do_{sub_id}_{n}")
    b.button(text=t("btn_menu", lang), callback_data="menu")
    b.adjust(3, 1)

    await call.message.edit_text(t("freeze_prompt", lang), reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("freeze_do_"))
async def freeze_do(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    parts = call.data.split("_")
    sub_id, days = int(parts[2]), int(parts[3])
    await state.clear()

    from db.queries import freeze_subscription
    sub = await freeze_subscription(session, sub_id, days)
    if not sub:
        await call.answer("Ошибка", show_alert=True)
        return

    date_str = sub.frozen_until.strftime("%d.%m.%Y") if sub.frozen_until else "—"
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_menu", lang), callback_data="menu")
    b.adjust(1)
    await call.message.edit_text(
        t("sub_frozen", lang, date=date_str),
        reply_markup=b.as_markup(),
    )
    await call.answer("❄️")


# ─────────────────────────────────────────────────────────────
# ПРОФИЛЬ
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery, db_user: User, **kwargs):
    lang = _lang(db_user)
    text = t(
        "profile_title", lang,
        name=db_user.full_name,
        gender=gender_label(db_user.gender, lang),
        level=level_label(db_user.fitness_level, lang),
        pref=pref_label(db_user.class_preference, lang),
        health=db_user.health_notes or "—",
        streak=db_user.streak_count or 0,
        lang=lang_label(lang, lang),
    )
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_edit_profile", lang),  callback_data="edit_profile")
    b.button(text="🌐 Язык / Language",          callback_data="change_language")
    b.button(text=t("btn_menu", lang),           callback_data="menu")
    b.adjust(1)
    await call.message.edit_text(text, reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data == "edit_profile")
async def edit_profile(call: CallbackQuery, state: FSMContext, db_user: User, **kwargs):
    db_user.onboarding_done = False
    from bot.handlers.onboarding import start_onboarding
    await call.message.delete()
    await start_onboarding(call.message, state)
    await call.answer()


# ─────────────────────────────────────────────────────────────
# ОТЗЫВ ПОСЛЕ ЗАНЯТИЯ
# ─────────────────────────────────────────────────────────────

class FeedbackFSM(StatesGroup):
    comment = State()


@router.callback_query(F.data.startswith("feedback_rate_"))
async def feedback_rate(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    parts = call.data.split("_")
    class_id, rating = int(parts[2]), int(parts[3])

    if await has_feedback(session, db_user.id, class_id):
        await call.answer(t("feedback_done", lang), show_alert=True)
        return

    await state.update_data(class_id=class_id, rating=rating)
    await state.set_state(FeedbackFSM.comment)

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_skip", lang), callback_data=f"feedback_skip_{class_id}")
    b.adjust(1)

    await call.message.edit_text(t("feedback_comment", lang), reply_markup=b.as_markup())
    await call.answer()


@router.message(FeedbackFSM.comment)
async def feedback_comment_text(message: Message, state: FSMContext, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    data = await state.get_data()
    await state.clear()
    await save_feedback(session, db_user.id, data["class_id"], data["rating"], message.text.strip())
    await message.answer(t("feedback_done", lang))


@router.callback_query(F.data.startswith("feedback_skip_"), FeedbackFSM.comment)
async def feedback_skip(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    data = await state.get_data()
    await state.clear()
    await save_feedback(session, db_user.id, data["class_id"], data["rating"], None)
    await call.message.edit_text(t("feedback_done", lang))
    await call.answer()


# ─────────────────────────────────────────────────────────────
# ИНДИВИДУАЛЬНЫЕ ЗАНЯТИЯ
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "individual")
async def individual_lesson(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    lang = _lang(db_user)
    from db.queries import get_setting
    trainer_tg = await get_setting(session, "trainer_telegram", "")
    b = InlineKeyboardBuilder()
    if trainer_tg:
        handle = trainer_tg.lstrip("@")
        b.button(text=t("btn_write_trainer", lang), url=f"https://t.me/{handle}")
    b.button(text=t("btn_menu", lang), callback_data="menu")
    b.adjust(1)
    await call.message.edit_text(t("individual_text", lang), reply_markup=b.as_markup())
    await call.answer()


# ─────────────────────────────────────────────────────────────
# КОНТАКТЫ
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "contacts")
async def contacts(call: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    from db.queries import get_setting
    name     = await get_setting(session, "studio_name",     settings.STUDIO_NAME)
    address  = await get_setting(session, "studio_address",  "—")
    phone    = await get_setting(session, "studio_phone",    "—")
    insta    = await get_setting(session, "studio_instagram", "—")
    schedule = await get_setting(session, "studio_schedule",  "—")
    lang = _lang(db_user)
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_menu", lang), callback_data="menu")
    b.adjust(1)
    await call.message.edit_text(
        f"📍 <b>{name}</b>\n\n"
        f"📍 Адрес: {address}\n"
        f"📞 Телефон: {phone}\n"
        f"💬 Instagram: {insta}\n\n"
        f"🕐 {schedule}",
        reply_markup=b.as_markup(),
    )
    await call.answer()
