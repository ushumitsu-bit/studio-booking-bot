"""
Онбординг-опросник для новых пользователей.
Запускается из /start если onboarding_done == False.
Шаги: язык → пол → уровень → формат → здоровье → готово.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.translations import t
from config import settings
from db.models import ClassPreference, FitnessLevel, Gender, User, UserLanguage

router = Router()


class OnboardingFSM(StatesGroup):
    language   = State()
    gender     = State()
    level      = State()
    preference = State()
    health     = State()


# ── Запуск онбординга ─────────────────────────────────────────────

async def start_onboarding(message: Message, state: FSMContext):
    await state.set_state(OnboardingFSM.language)
    b = InlineKeyboardBuilder()
    b.button(text="🇷🇺 Русский", callback_data="onb:lang:ru")
    b.button(text="🇺🇿 O'zbek",  callback_data="onb:lang:uz")
    b.button(text="🇬🇧 English", callback_data="onb:lang:en")
    b.adjust(1)
    await message.answer(
        t("choose_language", "ru"),
        reply_markup=b.as_markup(),
    )


# ── Шаг 1: язык ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("onb:lang:"), OnboardingFSM.language)
async def onb_language(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession, **kwargs):
    lang = call.data.split(":")[2]
    data = await state.get_data()

    if data.get("language_only"):
        # Только смена языка из профиля — не трогаем пол/уровень/предпочтения
        lang_map = {"ru": UserLanguage.RU, "uz": UserLanguage.UZ, "en": UserLanguage.EN}
        db_user.language = lang_map.get(lang, UserLanguage.RU)
        await session.commit()
        await state.clear()

        from bot.handlers.client import _main_menu_kb
        b = InlineKeyboardBuilder()
        b.button(text=t("btn_profile", lang), callback_data="profile")
        b.button(text=t("btn_menu", lang), callback_data="menu")
        b.adjust(1)
        await call.message.edit_text(t("language_changed", lang), reply_markup=b.as_markup())
        await call.answer()
        return

    await state.update_data(lang=lang)

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_female", lang), callback_data="onb:gender:female")
    b.button(text=t("btn_male",   lang), callback_data="onb:gender:male")
    b.adjust(2)

    await state.set_state(OnboardingFSM.gender)
    await call.message.edit_text(t("onb_gender", lang), reply_markup=b.as_markup())
    await call.answer()


# ── Шаг 2: пол ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("onb:gender:"), OnboardingFSM.gender)
async def onb_gender(call: CallbackQuery, state: FSMContext, **kwargs):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    gender = call.data.split(":")[2]
    await state.update_data(gender=gender)

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_lvl_beginner",     lang), callback_data="onb:lvl:beginner")
    b.button(text=t("btn_lvl_basic",        lang), callback_data="onb:lvl:basic")
    b.button(text=t("btn_lvl_intermediate", lang), callback_data="onb:lvl:intermediate")
    b.button(text=t("btn_lvl_advanced",     lang), callback_data="onb:lvl:advanced")
    b.adjust(1)

    await state.set_state(OnboardingFSM.level)
    await call.message.edit_text(t("onb_level", lang), reply_markup=b.as_markup())
    await call.answer()


# ── Шаг 3: уровень ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("onb:lvl:"), OnboardingFSM.level)
async def onb_level(call: CallbackQuery, state: FSMContext, **kwargs):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    level = call.data.split(":")[2]
    await state.update_data(level=level)

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_pref_group",      lang), callback_data="onb:pref:group")
    b.button(text=t("btn_pref_individual", lang), callback_data="onb:pref:individual")
    b.button(text=t("btn_pref_both",       lang), callback_data="onb:pref:both")
    b.adjust(1)

    await state.set_state(OnboardingFSM.preference)
    await call.message.edit_text(t("onb_preference", lang), reply_markup=b.as_markup())
    await call.answer()


# ── Шаг 4: предпочтение ──────────────────────────────────────────

@router.callback_query(F.data.startswith("onb:pref:"), OnboardingFSM.preference)
async def onb_preference(call: CallbackQuery, state: FSMContext, **kwargs):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    pref = call.data.split(":")[2]
    await state.update_data(pref=pref)

    b = InlineKeyboardBuilder()
    b.button(text=t("btn_skip", lang), callback_data="onb:health:skip")
    b.adjust(1)

    await state.set_state(OnboardingFSM.health)
    await call.message.edit_text(t("onb_health", lang), reply_markup=b.as_markup())
    await call.answer()


# ── Шаг 5а: здоровье — текст ─────────────────────────────────────

@router.message(OnboardingFSM.health)
async def onb_health_text(message: Message, state: FSMContext, db_user: User, session: AsyncSession, **kwargs):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    health = message.text.strip() if message.text else None
    await _finish_onboarding(message, state, session, db_user, lang, health)


# ── Шаг 5б: здоровье — пропуск ───────────────────────────────────

@router.callback_query(F.data == "onb:health:skip", OnboardingFSM.health)
async def onb_health_skip(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession, **kwargs):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await _finish_onboarding(call.message, state, session, db_user, lang, None, edit=True)
    await call.answer()


# ── Финал: сохранение + главное меню ─────────────────────────────

async def _finish_onboarding(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    lang: str,
    health: str | None,
    edit: bool = False,
):
    data = await state.get_data()
    await state.clear()

    gender_map = {"female": Gender.FEMALE, "male": Gender.MALE}
    level_map  = {
        "beginner":     FitnessLevel.BEGINNER,
        "basic":        FitnessLevel.BASIC,
        "intermediate": FitnessLevel.INTERMEDIATE,
        "advanced":     FitnessLevel.ADVANCED,
    }
    pref_map = {
        "group":      ClassPreference.GROUP,
        "individual": ClassPreference.INDIVIDUAL,
        "both":       ClassPreference.BOTH,
    }
    lang_map = {"ru": UserLanguage.RU, "uz": UserLanguage.UZ, "en": UserLanguage.EN}

    db_user.language          = lang_map.get(lang, UserLanguage.RU)
    db_user.gender            = gender_map.get(data.get("gender"))
    db_user.fitness_level     = level_map.get(data.get("level"))
    db_user.class_preference  = pref_map.get(data.get("pref"))
    db_user.health_notes      = health
    db_user.onboarding_done   = True
    await session.commit()

    first_name = db_user.full_name.split()[0] if db_user.full_name else "друг"
    text = t("onb_done", lang, name=first_name, studio=settings.STUDIO_NAME)

    from bot.handlers.client import _main_menu_kb
    kb = _main_menu_kb(lang)

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


# ── Смена языка (из профиля) ──────────────────────────────────────

@router.callback_query(F.data == "change_language")
async def change_language_start(call: CallbackQuery, state: FSMContext, db_user: User, **kwargs):
    lang = db_user.language.value if db_user.language else "ru"
    await state.set_state(OnboardingFSM.language)
    await state.update_data(language_only=True)  # только смена языка, профиль не перезаписывать
    b = InlineKeyboardBuilder()
    b.button(text="🇷🇺 Русский", callback_data="onb:lang:ru")
    b.button(text="🇺🇿 O'zbek",  callback_data="onb:lang:uz")
    b.button(text="🇬🇧 English", callback_data="onb:lang:en")
    b.adjust(1)
    await call.message.edit_text(t("choose_language", lang), reply_markup=b.as_markup())
    await call.answer()
