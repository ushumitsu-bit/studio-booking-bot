# 🕺 Studio Booking Bot — универсальный Telegram-бот для студии танцев

Полноценная CRM для студии: онбординг клиентов, расписание, запись, абонементы, оплата через **Payme**, QR-посещаемость, лист ожидания, заморозка, 3 языка интерфейса и панель администратора.

> Название студии и бота задаётся через `.env` — бот подходит для любой танцевальной студии или студии пилатеса.

---

## 🗂 Структура проекта

```
studio-booking-bot/
├── main.py                    # Точка входа — запуск бота + планировщика
├── webhook_app.py             # aiohttp — Payme JSON-RPC webhook (порт 8081)
├── miniapp_api.py             # FastAPI REST API для Telegram MiniApp (порт 8080)
├── config.py                  # Настройки (pydantic-settings + .env)
│
├── bot/
│   ├── handlers/
│   │   ├── client.py          # /start, расписание, запись, абонемент, профиль, отзыв
│   │   ├── onboarding.py      # FSM-опросник для новых пользователей
│   │   ├── admin.py           # Панель администратора
│   │   └── payments.py        # Оплата через Payme
│   ├── translations.py        # i18n: RU / UZ / EN — функция t(key, lang)
│   └── middlewares/
│       └── auth.py            # Авторизация, создание пользователя в БД
│
├── db/
│   ├── engine.py              # Подключение к PostgreSQL (asyncpg)
│   ├── models.py              # User, Class, Booking, Subscription, Payment, Waitlist, ClassFeedback
│   └── queries.py             # Все запросы к БД
│
├── services/
│   ├── payme.py               # Интеграция с Payme Business
│   ├── attendance.py          # HMAC QR-токены для отметки посещаемости
│   └── scheduler.py           # APScheduler: напоминания, отзывы, истечение абонементов
│
├── miniapp/
│   └── index.html             # Telegram WebApp (тёмная тема, календарь, QR-скан)
│
├── migrations/
│   └── versions/
│       ├── 001_initial.py
│       ├── 002_add_payme.py
│       ├── 003_subscription_plans.py
│       ├── 004_settings_and_class_fields.py
│       └── 005_user_features.py   # онбординг, лист ожидания, отзывы, заморозка
│
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## ⚙️ Настройка (.env)

```env
# Брендинг студии
STUDIO_NAME=Latina Mafia
BOT_NAME=Latina Mafia Bot

# Telegram
BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=[123456789]           # Telegram ID администраторов (через запятую)

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/studio_db

# Redis (FSM-состояния)
REDIS_URL=redis://localhost:6379

# Payme Business — https://merchant.payme.uz/
PAYME_MERCHANT_ID=your_merchant_id
PAYME_SECRET_KEY=your_secret_key
PAYME_RETURN_URL=https://t.me/your_bot

# Домен для webhook (HTTPS обязателен)
WEBHOOK_HOST=https://studio.yourdomain.uz
WEBHOOK_PATH=/payme/webhook

# Цены в сумах
PRICE_4_CLASSES=500000
PRICE_8_CLASSES=800000
PRICE_12_CLASSES=1100000
PRICE_16_CLASSES=1400000

# QR-посещаемость
ATTENDANCE_SECRET=сгенерируй: python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🎯 Ключевые возможности

### Для клиентов

| Функция | Описание |
|---------|---------|
| **Онбординг** | Опросник при первом запуске: язык → пол → уровень → формат → здоровье |
| **3 языка** | 🇷🇺 Русский / 🇺🇿 O'zbek / 🇬🇧 English — выбор при старте, смена в профиле |
| **Расписание** | Навигация по дням, статус мест (🟢🟡🔴), zoom-ссылка для онлайн-занятий |
| **Запись** | Один клик, списание с абонемента |
| **Лист ожидания** | Занятие заполнено → встать в очередь → уведомление при освобождении места |
| **Абонемент** | Прогресс-бар, срок действия, заморозка на 7/14/30 дней |
| **Отзывы** | ⭐ 1–5 + комментарий после каждого посещённого занятия |
| **Профиль** | Просмотр данных, редактирование, смена языка |
| **Индивидуальные** | Прямая ссылка на тренера в Telegram |

### Для администратора (`/admin`)

| Раздел | Возможности |
|--------|------------|
| **📅 Добавить занятие** | FSM: название → тренер → дата → время → места → локация → тип оплаты → zoom-ссылка |
| **📋 Расписание** | Занятия на 30 дней, детали, гендерный баланс группы, QR, ростер, отмена |
| **➕ Записать клиента** | Ручная запись любого пользователя на занятие (поиск по имени) |
| **👥 Клиенты** | Список с уровнем/полом, начисление занятий, заморозка/разморозка абонемента, блокировка |
| **📣 Рассылка** | Фильтры: всем / только девушкам / только парням / с абонементом / без / новичкам |
| **💰 Платежи** | История оплат через Payme |
| **📊 Статистика** | Клиенты, абонементы, посещаемость, пропуски, доход |
| **⚙️ Настройки** | Название, адрес, телефон, Instagram, тренеры, локации, шаблоны занятий, цены |

### Умные уведомления

| Событие | Действие |
|---------|---------|
| За 24ч до занятия | Напоминание клиенту |
| За 2ч до занятия | Второе напоминание |
| Пропуск без отмены | «Всё ок? Ждём тебя!» |
| Осталось ≤2 занятий | Предложение купить ещё |
| Абонемент истекает через ≤3 дня | Напоминание о продлении |
| **Парень записался** | Мгновенное уведомление всем ADMIN_IDS |

---

## 🕺 Гендерный баланс

Особенность для танцевальных студий — в карточке занятия администратор видит:

```
💃 Девушек: 5  ·  🕺 Парней: 2
  ⬜💃 Алия Каримова
  ✅🕺 Азиз Тошматов
  ...
```

При записи парня все администраторы получают мгновенное уведомление — удобно управлять парными занятиями.

---

## 🌐 Онбординг и профиль

Новый пользователь проходит 4-шаговый опросник:

```
Шаг 1 → Язык (🇷🇺 / 🇺🇿 / 🇬🇧)
Шаг 2 → Пол (💃 Девушка / 🕺 Парень)
Шаг 3 → Опыт (Новичок / До 6 мес / 6 мес–2 года / 2+ лет)
Шаг 4 → Формат (Групповые / Индивидуальные / Оба)
Шаг 5 → Ограничения по здоровью (текст или Пропустить)
```

Существующие пользователи опросник не видят. Данные редактируются через **👤 Мой профиль**.

---

## 💳 Payme Business

### Настройка
1. Зарегистрируйся на [merchant.payme.uz](https://merchant.payme.uz)
2. Личный кабинет → **Настройки** → **Ключи** → скопируй `Merchant ID` и `Secret Key`
3. Личный кабинет → **Уведомления**:
   - URL: `https://studio.yourdomain.uz/payme/webhook`
   - Логин: `Paycom` / Пароль: `PAYME_SECRET_KEY`

### Флоу оплаты

```
Клиент → Купить абонемент → выбирает тариф
  ↓
Бот создаёт Payment + "болванку" Subscription в БД
  ↓
Клиент переходит по Payme URL → платит (Uzcard / Humo / Visa)
  ↓
Payme → POST /payme/webhook → PerformTransaction
  ↓
confirm_payme_payment() → активирует абонемент на 30 дней
  ↓
Клиент получает: «Оплата прошла! 🎉»
```

> **Тестовая карта Uzcard:** `8600 4954 7331 6478`, любой срок, CVV `000`

---

## 📱 Telegram MiniApp

Кнопка **Открыть студию** в главном меню.

**Экраны:** расписание с записью/отменой, мои занятия + QR-отметка, абонемент + оплата.

**Технологии:** нативный JS + Telegram WebApp API, тёмная тема.

---

## 🗄 База данных

```
users          — клиенты (профиль, язык, пол, уровень, streak)
  ├── bookings      — записи на занятия  ←→  classes
  ├── subscriptions — абонементы (с заморозкой)
  ├── payments      — история платежей Payme
  ├── waitlist      — лист ожидания на занятие
  └── class_feedback— отзывы (1–5 звёзд + комментарий)

settings       — настройки студии (ключ-значение)
```

```bash
alembic upgrade head       # Применить все миграции
alembic downgrade -1       # Откатить последнюю
```

---

## 🚀 Деплой на VPS

### Требования
- Ubuntu 22.04 LTS, 1 vCPU / 1 GB RAM
- Публичный IP + домен с A-записью → `WEBHOOK_HOST`

### Быстрый деплой
```bash
git clone https://github.com/ushumitsu-bit/studio-booking-bot.git /opt/studio-bot
cd /opt/studio-bot
cp .env.example .env && nano .env
bash scripts/deploy.sh
```

### Обновление
```bash
cd /opt/studio-bot
git pull
docker compose up -d --build bot webhook
docker compose exec bot alembic upgrade head
```

### Управление
```bash
docker compose logs -f bot       # Логи бота
docker compose restart bot       # Рестарт
docker compose ps                # Статус
```

---

## 🏃 Локальная разработка

```bash
# 1. Зависимости
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. PostgreSQL + Redis
docker run -d --name pg -e POSTGRES_USER=studio -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=studio_db -p 5432:5432 postgres:16-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 3. .env
cp .env.example .env  # заполни BOT_TOKEN и PAYME_*

# 4. Миграции
alembic upgrade head

# 5. Запуск
python main.py                  # бот
python webhook_runner.py        # webhook + miniapp API
```

Для теста Payme локально:
```bash
ngrok http 8081
# Скопируй HTTPS URL → WEBHOOK_HOST в .env
```

---

## 📦 Стек

| Компонент | Технология |
|-----------|-----------|
| Бот | aiogram 3.x (async, FSM) |
| База данных | PostgreSQL 16 + SQLAlchemy 2 (asyncpg) |
| FSM / кэш | Redis |
| Платежи | Payme Business (Subscribe API) |
| MiniApp backend | FastAPI + uvicorn |
| Webhook-сервер | aiohttp |
| Планировщик | APScheduler 3 |
| Миграции | Alembic |
| Деплой | Docker Compose + Nginx + Let's Encrypt |

---

## ❓ FAQ

**Как сменить название студии?**
Измени `STUDIO_NAME` в `.env` и перезапусти бот — без пересборки образа.

**Как протестировать оплату?**
Используй TEST-ключи из кабинета Payme. Карта: `8600 4954 7331 6478`.

**Как добавить тренера / локацию?**
`/admin` → ⚙️ Настройки → поля «Тренеры» и «Студии/локации» (через `|`).

**Бот не видит новых пользователей после деплоя?**
Убедись что миграция применена: `docker compose exec bot alembic upgrade head`.
