"""
Переводы интерфейса бота на 3 языка: ru / uz / en.
Использование: t("key", lang, param=value)
"""

_T: dict[str, dict[str, str]] = {
    # ── Выбор языка ──────────────────────────────────────────────
    "choose_language": {
        "ru": "🌐 Выбери язык / Tilni tanlang / Choose language:",
        "uz": "🌐 Выбери язык / Tilni tanlang / Choose language:",
        "en": "🌐 Выбери язык / Tilni tanlang / Choose language:",
    },
    "btn_lang_ru": {"ru": "🇷🇺 Русский", "uz": "🇷🇺 Русский", "en": "🇷🇺 Русский"},
    "btn_lang_uz": {"ru": "🇺🇿 O'zbek",  "uz": "🇺🇿 O'zbek",  "en": "🇺🇿 O'zbek"},
    "btn_lang_en": {"ru": "🇬🇧 English", "uz": "🇬🇧 English", "en": "🇬🇧 English"},

    # ── Онбординг ────────────────────────────────────────────────
    "onb_gender": {
        "ru": "👤 <b>Шаг 1/4 — Расскажи о себе</b>\n\nКто ты?",
        "uz": "👤 <b>1/4-qadam — O'zing haqingda gapir</b>\n\nSen kimsan?",
        "en": "👤 <b>Step 1/4 — Tell us about you</b>\n\nWho are you?",
    },
    "btn_female": {
        "ru": "💃 Девушка",
        "uz": "💃 Qiz",
        "en": "💃 Female",
    },
    "btn_male": {
        "ru": "🕺 Парень",
        "uz": "🕺 Yigit",
        "en": "🕺 Male",
    },
    "onb_level": {
        "ru": "🧘 <b>Шаг 2/4 — Опыт занятий</b>\n\nКакой у тебя опыт в танцах / пилатесе?",
        "uz": "🧘 <b>2/4-qadam — Tajriba</b>\n\nRaqs / pilates bo'yicha tajribang qanday?",
        "en": "🧘 <b>Step 2/4 — Experience</b>\n\nWhat's your dance / pilates experience?",
    },
    "btn_lvl_beginner": {
        "ru": "🌱 Новичок — ещё не занимался(ась)",
        "uz": "🌱 Yangi boshlayotgan — hech qachon shug'ullanmagan",
        "en": "🌱 Beginner — never tried",
    },
    "btn_lvl_basic": {
        "ru": "📗 Немного — до 6 месяцев",
        "uz": "📗 Ozgina — 6 oygacha",
        "en": "📗 A little — up to 6 months",
    },
    "btn_lvl_intermediate": {
        "ru": "📘 Регулярно — 6 мес – 2 года",
        "uz": "📘 Muntazam — 6 oy – 2 yil",
        "en": "📘 Regular — 6 months to 2 years",
    },
    "btn_lvl_advanced": {
        "ru": "📕 Давно — 2+ лет",
        "uz": "📕 Uzoq vaqt — 2+ yil",
        "en": "📕 Advanced — 2+ years",
    },
    "onb_preference": {
        "ru": "💃 <b>Шаг 3/4 — Формат занятий</b>\n\nЧто тебе больше интересно?",
        "uz": "💃 <b>3/4-qadam — Dars formati</b>\n\nQaysi format sizga ko'proq mos keladi?",
        "en": "💃 <b>Step 3/4 — Class format</b>\n\nWhat interests you more?",
    },
    "btn_pref_group": {
        "ru": "👥 Групповые занятия",
        "uz": "👥 Guruh darslari",
        "en": "👥 Group classes",
    },
    "btn_pref_individual": {
        "ru": "🧑 Индивидуальные",
        "uz": "🧑 Individual",
        "en": "🧑 Individual",
    },
    "btn_pref_both": {
        "ru": "✨ Оба варианта",
        "uz": "✨ Ikkalasi ham",
        "en": "✨ Both",
    },
    "onb_health": {
        "ru": (
            "💊 <b>Шаг 4/4 — Здоровье (необязательно)</b>\n\n"
            "Есть ли травмы или ограничения по здоровью, о которых тренеру нужно знать?\n\n"
            "Напиши текстом или нажми <b>Пропустить</b>."
        ),
        "uz": (
            "💊 <b>4/4-qadam — Sog'liq (ixtiyoriy)</b>\n\n"
            "Murabbiy bilishi kerak bo'lgan shikastlanishlar yoki cheklovlar bormi?\n\n"
            "Matn yozing yoki <b>O'tkazib yuborish</b> tugmasini bosing."
        ),
        "en": (
            "💊 <b>Step 4/4 — Health (optional)</b>\n\n"
            "Any injuries or health restrictions the trainer should know about?\n\n"
            "Type your answer or tap <b>Skip</b>."
        ),
    },
    "btn_skip": {
        "ru": "⏭ Пропустить",
        "uz": "⏭ O'tkazib yuborish",
        "en": "⏭ Skip",
    },
    "onb_done": {
        "ru": (
            "🎉 <b>Отлично, {name}!</b>\n\n"
            "Всё готово — добро пожаловать в <b>{studio}</b>!\n\n"
            "📅 Расписание, запись на занятия и абонемент — всё здесь 👇"
        ),
        "uz": (
            "🎉 <b>Zo'r, {name}!</b>\n\n"
            "Hammasi tayyor — <b>{studio}</b> ga xush kelibsiz!\n\n"
            "📅 Jadval, darsga yozilish va obuna — hammasi shu yerda 👇"
        ),
        "en": (
            "🎉 <b>Great, {name}!</b>\n\n"
            "All set — welcome to <b>{studio}</b>!\n\n"
            "📅 Schedule, booking and subscription — all right here 👇"
        ),
    },

    # ── Главное меню ─────────────────────────────────────────────
    "welcome_back": {
        "ru": (
            "💃 Привет, <b>{name}</b>! Добро пожаловать в <b>{studio}</b>.\n\n"
            "📅 <b>Расписание</b> — занятия и запись\n"
            "🗓 <b>Мои записи</b> — управление записями\n"
            "💳 <b>Абонемент</b> — купить и отслеживать\n\n"
            "👇 Нажми кнопку ниже чтобы открыть приложение"
        ),
        "uz": (
            "💃 Salom, <b>{name}</b>! <b>{studio}</b> ga xush kelibsiz.\n\n"
            "📅 <b>Jadval</b> — darslar va yozilish\n"
            "🗓 <b>Mening yozuvlarim</b> — yozuvlarni boshqarish\n"
            "💳 <b>Obuna</b> — sotib olish va kuzatish\n\n"
            "👇 Ilovani ochish uchun quyidagi tugmani bosing"
        ),
        "en": (
            "💃 Hi, <b>{name}</b>! Welcome to <b>{studio}</b>.\n\n"
            "📅 <b>Schedule</b> — classes and booking\n"
            "🗓 <b>My bookings</b> — manage your bookings\n"
            "💳 <b>Subscription</b> — buy and track\n\n"
            "👇 Tap the button below to open the app"
        ),
    },
    "main_menu_title": {
        "ru": "🏠 <b>Главное меню</b>\n\nЧто хочешь сделать, {name}?\n\n👇 Нажми на нужную кнопку",
        "uz": "🏠 <b>Bosh menyu</b>\n\nNima qilmoqchisan, {name}?\n\n👇 Kerakli tugmani bosing",
        "en": "🏠 <b>Main menu</b>\n\nWhat would you like to do, {name}?\n\n👇 Tap a button",
    },
    "btn_schedule":    {"ru": "📅 Расписание и запись",   "uz": "📅 Jadval va yozilish",      "en": "📅 Schedule & booking"},
    "btn_my_bookings": {"ru": "🗓 Мои записи",            "uz": "🗓 Mening yozuvlarim",        "en": "🗓 My bookings"},
    "btn_my_sub":      {"ru": "💳 Абонемент / Оплата",   "uz": "💳 Obuna / To'lov",           "en": "💳 Subscription / Pay"},
    "btn_individual":  {"ru": "🧘 Индивидуальные занятия","uz": "🧘 Individual darslar",       "en": "🧘 Individual classes"},
    "btn_contacts":    {"ru": "📞 Контакты студии",       "uz": "📞 Studiya kontaktlari",      "en": "📞 Studio contacts"},
    "btn_profile":     {"ru": "👤 Мой профиль",          "uz": "👤 Mening profilim",           "en": "👤 My profile"},
    "btn_menu":        {"ru": "← Меню",                  "uz": "← Menyu",                      "en": "← Menu"},
    "btn_open_app":    {"ru": "🕺 Открыть {studio}",     "uz": "🕺 {studio} ochish",           "en": "🕺 Open {studio}"},

    # ── Расписание ───────────────────────────────────────────────
    "no_classes": {
        "ru": "😔 На ближайшие 2 недели занятий нет.\n\nСледи за обновлениями!",
        "uz": "😔 Yaqin 2 hafta ichida darslar yo'q.\n\nYangilanishlarni kuzating!",
        "en": "😔 No classes in the next 2 weeks.\n\nStay tuned for updates!",
    },
    "spots_none":  {"ru": "нет мест", "uz": "joy yo'q",    "en": "no spots"},
    "spots_count": {"ru": "{n} мест", "uz": "{n} joy",      "en": "{n} spots"},
    "you_booked":  {"ru": " ✅ <i>ты записана</i>",         "uz": " ✅ <i>yozilgansiz</i>",    "en": " ✅ <i>booked</i>"},
    "today_label": {"ru": " (сегодня)", "uz": " (bugun)",   "en": " (today)"},
    "btn_today":   {"ru": "📅 Сегодня",  "uz": "📅 Bugun",  "en": "📅 Today"},

    # ── Запись ───────────────────────────────────────────────────
    "no_spots_alert": {
        "ru": "😔 Мест нет. Попробуй другое занятие!",
        "uz": "😔 Joy yo'q. Boshqa darsni sinab ko'ring!",
        "en": "😔 No spots left. Try another class!",
    },
    "already_booked": {
        "ru": "✅ Ты уже записана на это занятие!",
        "uz": "✅ Siz allaqachon bu darsga yozilgansiz!",
        "en": "✅ You are already booked for this class!",
    },
    "confirm_booking": {
        "ru": "📌 <b>Подтверди запись:</b>\n\n🧘 {title}\n📅 {dt}\n👤 Тренер: {trainer}\n{spots_icon} Мест: {spots}/{max}\n\n{sub_info}",
        "uz": "📌 <b>Yozilishni tasdiqlang:</b>\n\n🧘 {title}\n📅 {dt}\n👤 Murabbiy: {trainer}\n{spots_icon} Joy: {spots}/{max}\n\n{sub_info}",
        "en": "📌 <b>Confirm booking:</b>\n\n🧘 {title}\n📅 {dt}\n👤 Trainer: {trainer}\n{spots_icon} Spots: {spots}/{max}\n\n{sub_info}",
    },
    "sub_ok": {
        "ru": "✅ Абонемент: <b>{n} занятий</b> осталось",
        "uz": "✅ Obuna: <b>{n} dars</b> qoldi",
        "en": "✅ Subscription: <b>{n} classes</b> left",
    },
    "sub_none": {
        "ru": "⚠️ <b>Активного абонемента нет.</b>\nОплати занятие через кнопку 💳 Оплатить",
        "uz": "⚠️ <b>Faol obuna yo'q.</b>\n💳 To'lash tugmasi orqali to'lang",
        "en": "⚠️ <b>No active subscription.</b>\nPay via the 💳 Pay button",
    },
    "btn_book_confirm": {"ru": "✅ Записаться",       "uz": "✅ Yozilish",   "en": "✅ Book"},
    "btn_buy_sub":      {"ru": "💳 Купить абонемент", "uz": "💳 Obuna sotib olish", "en": "💳 Buy subscription"},
    "btn_schedule":     {"ru": "← Расписание",        "uz": "← Jadval",     "en": "← Schedule"},
    "booked_ok": {
        "ru": "🎉 <b>Ты записана!</b>\n\n🧘 {title}\n📅 {dt}\n👤 Тренер: {trainer}\n\n⏰ Напомню за 24 часа и за 2 часа до занятия.",
        "uz": "🎉 <b>Yozildingiz!</b>\n\n🧘 {title}\n📅 {dt}\n👤 Murabbiy: {trainer}\n\n⏰ Darsdan 24 va 2 soat oldin eslataman.",
        "en": "🎉 <b>You're booked!</b>\n\n🧘 {title}\n📅 {dt}\n👤 Trainer: {trainer}\n\n⏰ I'll remind you 24h and 2h before class.",
    },
    "no_spots_full": {
        "ru": "😔 Мест уже нет!",
        "uz": "😔 Joy qolmadi!",
        "en": "😔 No spots left!",
    },

    # ── Лист ожидания ────────────────────────────────────────────
    "waitlist_prompt": {
        "ru": "🔴 Мест нет, но ты можешь встать в <b>лист ожидания</b>.\nКак только кто-то отменит — ты первая узнаешь!",
        "uz": "🔴 Joy yo'q, lekin <b>kutish ro'yxati</b>ga kirishingiz mumkin.\nBirov bekor qilsa — siz birinchi bo'lib bilib olasiz!",
        "en": "🔴 No spots left, but you can join the <b>waitlist</b>.\nYou'll be first to know when a spot opens!",
    },
    "btn_join_waitlist": {
        "ru": "🔔 Встать в очередь",
        "uz": "🔔 Navbatga kirish",
        "en": "🔔 Join waitlist",
    },
    "waitlist_joined": {
        "ru": "✅ Ты в листе ожидания!\nУведомим как только освободится место.",
        "uz": "✅ Siz kutish ro'yxatidasiz!\nJoy bo'shashuvi haqida xabar beramiz.",
        "en": "✅ You're on the waitlist!\nWe'll notify you when a spot opens.",
    },
    "waitlist_already": {
        "ru": "ℹ️ Ты уже в листе ожидания на это занятие.",
        "uz": "ℹ️ Siz allaqachon bu dars uchun kutish ro'yxatidasiz.",
        "en": "ℹ️ You're already on the waitlist for this class.",
    },
    "waitlist_notify": {
        "ru": "🔔 <b>Место освободилось!</b>\n\n🧘 {title}\n📅 {dt}\n\nЗапишись пока не заняли 👇",
        "uz": "🔔 <b>Joy bo'shadi!</b>\n\n🧘 {title}\n📅 {dt}\n\nBand qilinmagunicha yozilib oling 👇",
        "en": "🔔 <b>A spot opened up!</b>\n\n🧘 {title}\n📅 {dt}\n\nBook before it's gone 👇",
    },
    "btn_book_now": {"ru": "✅ Записаться сейчас", "uz": "✅ Hozir yozilish", "en": "✅ Book now"},

    # ── Мои записи ───────────────────────────────────────────────
    "no_bookings": {
        "ru": "🗓 <b>Предстоящих занятий нет.</b>\n\nЗапишись через расписание 📅",
        "uz": "🗓 <b>Kelgusi darslar yo'q.</b>\n\n📅 Jadval orqali yoziling",
        "en": "🗓 <b>No upcoming classes.</b>\n\nBook via the schedule 📅",
    },
    "my_bookings_title": {
        "ru": "🗓 <b>Твои ближайшие занятия:</b>\n",
        "uz": "🗓 <b>Yaqindagi darslaringiz:</b>\n",
        "en": "🗓 <b>Your upcoming classes:</b>\n",
    },
    "cancel_confirm_prompt": {
        "ru": "Отменить запись?\n\n🧘 {title}\n📅 {dt}\n👤 {trainer}",
        "uz": "Yozilishni bekor qilasizmi?\n\n🧘 {title}\n📅 {dt}\n👤 {trainer}",
        "en": "Cancel booking?\n\n🧘 {title}\n📅 {dt}\n👤 {trainer}",
    },
    "btn_yes_cancel": {"ru": "✅ Да, отменить",    "uz": "✅ Ha, bekor qilish",  "en": "✅ Yes, cancel"},
    "cancel_done": {
        "ru": "✅ <b>Запись отменена.</b>\n\nМесто освобождено для других. До встречи! 💛",
        "uz": "✅ <b>Yozilish bekor qilindi.</b>\n\nJoy boshqalar uchun bo'shadi. Ko'rishguncha! 💛",
        "en": "✅ <b>Booking cancelled.</b>\n\nSpot freed for others. See you! 💛",
    },

    # ── Абонемент ────────────────────────────────────────────────
    "no_sub": {
        "ru": "💳 <b>Активного абонемента нет.</b>\n\nКупи абонемент прямо здесь — быстро и безопасно 👇",
        "uz": "💳 <b>Faol obuna yo'q.</b>\n\nShu yerda tezda va xavfsiz obuna sotib oling 👇",
        "en": "💳 <b>No active subscription.</b>\n\nBuy one right here — fast and secure 👇",
    },
    "sub_status": {
        "ru": "📊 <b>Твой абонемент</b>\n\n{bar}\n✅ Осталось занятий: <b>{left}</b>\n📅 Действует до: <b>{expires}</b>\n\nЗаписывайся на занятия пока есть места! 🧘",
        "uz": "📊 <b>Sizning obunangiz</b>\n\n{bar}\n✅ Darslar qoldi: <b>{left}</b>\n📅 Amal qilish muddati: <b>{expires}</b>\n\nJoy borken yoziling! 🧘",
        "en": "📊 <b>Your subscription</b>\n\n{bar}\n✅ Classes left: <b>{left}</b>\n📅 Valid until: <b>{expires}</b>\n\nBook while spots are available! 🧘",
    },
    "sub_frozen": {
        "ru": "❄️ <b>Абонемент заморожен</b> до {date}.\n\nОбратись к администратору для разморозки.",
        "uz": "❄️ <b>Obuna muzlatilgan</b> {date} gacha.\n\nMuzlatishni bekor qilish uchun administratorga murojaat qiling.",
        "en": "❄️ <b>Subscription frozen</b> until {date}.\n\nContact the admin to unfreeze.",
    },
    "btn_buy_more":  {"ru": "💳 Купить ещё",  "uz": "💳 Yana sotib olish",  "en": "💳 Buy more"},
    "btn_freeze":    {"ru": "❄️ Заморозить",  "uz": "❄️ Muzlatish",         "en": "❄️ Freeze"},
    "freeze_prompt": {
        "ru": "❄️ <b>Заморозка абонемента</b>\n\nНа сколько дней заморозить?\n(Срок действия продлится на это время)",
        "uz": "❄️ <b>Obunani muzlatish</b>\n\nNecha kunga muzlatish?\n(Amal qilish muddati shu vaqtga uzayadi)",
        "en": "❄️ <b>Freeze subscription</b>\n\nFor how many days?\n(Expiry date will be extended by this amount)",
    },

    # ── Профиль ──────────────────────────────────────────────────
    "profile_title": {
        "ru": "👤 <b>Мой профиль</b>\n\n👤 {name}\n🚻 Пол: {gender}\n🧘 Уровень: {level}\n💃 Формат: {pref}\n💊 Здоровье: {health}\n🔥 Серия: {streak} зан.\n🌐 Язык: {lang}",
        "uz": "👤 <b>Mening profilim</b>\n\n👤 {name}\n🚻 Jins: {gender}\n🧘 Daraja: {level}\n💃 Format: {pref}\n💊 Sog'liq: {health}\n🔥 Seriya: {streak} dars\n🌐 Til: {lang}",
        "en": "👤 <b>My profile</b>\n\n👤 {name}\n🚻 Gender: {gender}\n🧘 Level: {level}\n💃 Format: {pref}\n💊 Health: {health}\n🔥 Streak: {streak} classes\n🌐 Language: {lang}",
    },
    "btn_edit_profile": {
        "ru": "✏️ Изменить профиль",
        "uz": "✏️ Profilni tahrirlash",
        "en": "✏️ Edit profile",
    },
    "profile_gender_female": {"ru": "Девушка 💃", "uz": "Qiz 💃",   "en": "Female 💃"},
    "profile_gender_male":   {"ru": "Парень 🕺",  "uz": "Yigit 🕺", "en": "Male 🕺"},
    "profile_gender_none":   {"ru": "—",           "uz": "—",        "en": "—"},
    "level_beginner":     {"ru": "Новичок",    "uz": "Yangi",      "en": "Beginner"},
    "level_basic":        {"ru": "Базовый",    "uz": "Asosiy",     "en": "Basic"},
    "level_intermediate": {"ru": "Средний",   "uz": "O'rta",      "en": "Intermediate"},
    "level_advanced":     {"ru": "Продвинутый","uz": "Ilg'or",    "en": "Advanced"},
    "pref_group":         {"ru": "Групповые",  "uz": "Guruh",      "en": "Group"},
    "pref_individual":    {"ru": "Индивидуальные", "uz": "Individual", "en": "Individual"},
    "pref_both":          {"ru": "Оба",        "uz": "Ikkalasi",   "en": "Both"},
    "lang_ru": {"ru": "Русский", "uz": "Ruscha", "en": "Russian"},
    "lang_uz": {"ru": "Узбекский", "uz": "O'zbek", "en": "Uzbek"},
    "lang_en": {"ru": "Английский", "uz": "Inglizcha", "en": "English"},

    # ── Отзыв после занятия ──────────────────────────────────────
    "feedback_request": {
        "ru": "⭐ Как прошло занятие?\n\n🧘 <b>{title}</b> · {dt}\n\nПоставь оценку:",
        "uz": "⭐ Dars qanday o'tdi?\n\n🧘 <b>{title}</b> · {dt}\n\nBaho bering:",
        "en": "⭐ How was the class?\n\n🧘 <b>{title}</b> · {dt}\n\nRate it:",
    },
    "feedback_comment": {
        "ru": "✍️ Хочешь добавить комментарий? (или нажми Пропустить)",
        "uz": "✍️ Izoh qo'shmoqchimisiz? (yoki O'tkazib yuborishni bosing)",
        "en": "✍️ Want to add a comment? (or tap Skip)",
    },
    "feedback_done": {
        "ru": "🙏 Спасибо за отзыв! Это помогает нам становиться лучше.",
        "uz": "🙏 Fikr-mulohaza uchun rahmat! Bu bizga yaxshilanishga yordam beradi.",
        "en": "🙏 Thanks for your feedback! It helps us improve.",
    },

    # ── Индивидуальные занятия ───────────────────────────────────
    "individual_text": {
        "ru": "🧘 <b>Индивидуальные занятия</b>\n\nПерсональные тренировки — занятие составляется под тебя:\nуровень, цели, травмы и пожелания учитываются полностью.\n\nДля записи и уточнения расписания напиши тренеру напрямую 👇",
        "uz": "🧘 <b>Individual darslar</b>\n\nShaxsiy trenirovkalar — dars siz uchun tuziladi:\ndara, maqsad, jarohatlar va xohishlar to'liq hisobga olinadi.\n\nYozilish va jadval uchun murabbiyga to'g'ridan-to'g'ri yozing 👇",
        "en": "🧘 <b>Individual classes</b>\n\nPersonal training — tailored just for you:\nlevel, goals, injuries and preferences all taken into account.\n\nMessage the trainer directly to book 👇",
    },
    "btn_write_trainer": {
        "ru": "✍️ Написать тренеру",
        "uz": "✍️ Murabbiyga yozish",
        "en": "✍️ Message trainer",
    },

    # ── Онлайн занятие ───────────────────────────────────────────
    "zoom_link_label": {
        "ru": "🎥 Онлайн: {link}",
        "uz": "🎥 Onlayn: {link}",
        "en": "🎥 Online: {link}",
    },
}


def t(key: str, lang: str = "ru", **kwargs) -> str:
    lang = lang if lang in ("ru", "uz", "en") else "ru"
    row = _T.get(key, {})
    text = row.get(lang) or row.get("ru") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def gender_label(gender, lang: str = "ru") -> str:
    from db.models import Gender
    if gender == Gender.FEMALE:
        return t("profile_gender_female", lang)
    if gender == Gender.MALE:
        return t("profile_gender_male", lang)
    return t("profile_gender_none", lang)


def level_label(level, lang: str = "ru") -> str:
    from db.models import FitnessLevel
    mapping = {
        FitnessLevel.BEGINNER:     "level_beginner",
        FitnessLevel.BASIC:        "level_basic",
        FitnessLevel.INTERMEDIATE: "level_intermediate",
        FitnessLevel.ADVANCED:     "level_advanced",
    }
    return t(mapping.get(level, "level_beginner"), lang) if level else "—"


def pref_label(pref, lang: str = "ru") -> str:
    from db.models import ClassPreference
    mapping = {
        ClassPreference.GROUP:      "pref_group",
        ClassPreference.INDIVIDUAL: "pref_individual",
        ClassPreference.BOTH:       "pref_both",
    }
    return t(mapping.get(pref, "pref_group"), lang) if pref else "—"


def lang_label(lang_code: str, display_lang: str = "ru") -> str:
    mapping = {"ru": "lang_ru", "uz": "lang_uz", "en": "lang_en"}
    return t(mapping.get(lang_code, "lang_ru"), display_lang)
