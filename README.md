# 🧘 Pilates Bot — Telegram-бот для студии пилатеса

Полноценная система управления студией пилатеса:
запись клиентов, расписание, Telegram MiniApp, оплата через **Payme**, QR-посещаемость и автонапоминания.

---

## 🗂 Структура проекта

```
pilates-bot/
├── main.py                    # Точка входа — запуск бота + планировщика
├── webhook_app.py             # FastAPI (miniapp API) + aiohttp (Payme webhook)
├── miniapp_api.py             # REST API для Telegram WebApp
├── config.py                  # Настройки (pydantic-settings + .env)
│
├── bot/
│   ├── handlers/
│   │   ├── client.py          # /start, расписание, запись, абонемент, инд. занятия
│   │   ├── admin.py           # Панель администратора (FSM, QR, ростер)
│   │   └── payments.py        # Оплата через Payme
│   ├── keyboards/
│   │   └── inline.py          # Все inline-клавиатуры
│   └── middlewares/
│       └── auth.py            # Авторизация, создание пользователя в БД
│
├── db/
│   ├── engine.py              # Подключение к PostgreSQL (asyncpg)
│   ├── models.py              # SQLAlchemy-модели: User, Class, Booking, Subscription, Payment
│   └── queries.py             # Все запросы к БД
│
├── services/
│   ├── payme.py               # Интеграция с Payme Business (URL + JSON-RPC webhook)
│   ├── attendance.py          # HMAC QR-токены для отметки посещаемости
│   └── scheduler.py          # APScheduler: напоминания, пинки, истечение абонементов
│
├── miniapp/
│   └── index.html             # Telegram WebApp (тёмная тема, календарь, QR-скан)
│
├── migrations/
│   └── versions/
│       ├── 001_initial.py     # Создание всех таблиц
│       ├── 002_add_payme.py   # Замена yukassa_id → payme_id
│       └── 003_subscription_plans.py  # pack_12, pack_16, low_classes_warned
│
├── scripts/
│   └── deploy.sh              # Автодеплой на VPS (Ubuntu 22+)
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

Скопируй `.env.example` → `.env` и заполни:

```env
# Telegram
BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=[123456789]           # Твой Telegram ID (узнать: @userinfobot)

# PostgreSQL (менять только если не docker-compose)
DATABASE_URL=postgresql+asyncpg://pilates:password@localhost:5432/pilates_db

# Redis
REDIS_URL=redis://localhost:6379

# Payme Business — личный кабинет: https://merchant.payme.uz/
PAYME_MERCHANT_ID=your_merchant_id
PAYME_SECRET_KEY=your_secret_key    # TEST_KEY или PROD_KEY
PAYME_RETURN_URL=https://t.me/your_bot

# Домен для webhook (нужен HTTPS)
WEBHOOK_HOST=https://pilates.yourdomain.uz
WEBHOOK_PATH=/payme/webhook

# Цены в сумах (абонементы на 30 дней)
PRICE_4_CLASSES=500000
PRICE_8_CLASSES=800000
PRICE_12_CLASSES=1100000
PRICE_16_CLASSES=1400000

# QR-посещаемость (случайная строка)
ATTENDANCE_SECRET=сгенерируй: python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 💳 Настройка Payme Business (пошагово)

### 1. Регистрация
Зайди на [merchant.payme.uz](https://merchant.payme.uz) → создай магазин → пройди верификацию.

### 2. Получи ключи
Личный кабинет → **Настройки** → **Ключи**:
- `Merchant ID` → `PAYME_MERCHANT_ID`
- `Секретный ключ` → `PAYME_SECRET_KEY`

> **Тестирование:** используй TEST-ключи из кабинета.
> Тестовая карта Uzcard: `8600 4954 7331 6478`, любой срок, CVV `000`

### 3. Настрой webhook
Личный кабинет → **Настройки** → **Уведомления**:
- URL: `https://pilates.yourdomain.uz/payme/webhook`
- Логин: `Paycom`  
- Пароль: твой `PAYME_SECRET_KEY`

### 4. Как работает оплата

```
Клиент → Купить абонемент → выбирает тариф
  ↓
Бот создаёт Payment в БД и формирует checkout URL
  ↓
Клиент переходит → платит (Uzcard, Humo, Visa/MC)
  ↓
Payme POST /payme/webhook → PerformTransaction
  ↓
Бот: confirm_payme_payment() → активирует абонемент (30 дней)
  ↓
Клиент получает сообщение "Оплата прошла! 🎉"
```

---

## 📱 Telegram MiniApp

Доступен по кнопке **🌐 Открыть приложение** в главном меню бота.

**Экраны:**
- **Главная** — имя, остаток занятий, ближайшая запись
- **Расписание** — календарь с отметками занятий, запись/отмена
- **Мои записи** — список предстоящих занятий, кнопка QR-отметки
- **Абонемент** — прогресс-бар, история, кнопка оплаты

**Технологии:** нативный JS + Telegram WebApp API, тёмная тема (`#0B0B14` + золото `#C9A84C`).

---

## 📷 QR-посещаемость

**Флоу:**
1. Тренер открывает занятие в `/admin` → нажимает **📱 QR явка** → бот присылает QR-код
2. Студентка сканирует QR камерой или через кнопку **Отметиться** в MiniApp
3. MiniApp открывается с параметром `?attend=TOKEN` → автоматически отмечает явку
4. Если опоздала — тренер отмечает вручную через **✅ Отметить вручную** → ростер со списком

**Безопасность токена:** HMAC-SHA256, действует 2 часа, не хранится в БД.

---

## 🔔 Автоматические напоминания

| Триггер | Когда | Действие |
|---------|-------|---------|
| **Напоминание 24ч** | За 24 ч до занятия | «Напоминаю о занятии завтра!» |
| **Напоминание 2ч** | За 2 ч до занятия | «Через 2 часа — пилатес!» |
| **Пинок** | Занятие прошло, не пришла | «Ты не пришла... всё ок?» |
| **Мало занятий** | Осталось ≤2 занятий | «Занятия заканчиваются!» + кнопка «Купить» |
| **Абонемент истекает** | ≤3 дня до конца срока | «Абонемент истекает 28.05!» + кнопка «Продлить» |

Все задачи — APScheduler в фоне бота, каждое уведомление каждому пользователю приходит один раз.

---

## 👩‍💼 Панель администратора (`/admin`)

| Раздел | Возможности |
|--------|------------|
| **📅 Добавить занятие** | FSM-диалог: название → тренер → дата → время → места → локация/тип оплаты |
| **📋 Расписание** | Занятия на 14 дней, детали, QR, ростер, отмена занятия |
| **👥 Клиенты** | Список (✅ есть абонемент / ⚠️ нет), начисление занятий, блокировка |
| **💰 Платежи** | История оплат за месяц |
| **📣 Рассылка** | HTML-сообщение всем активным клиентам |
| **📊 Статистика** | Клиенты, абонементы, пропуски, общий доход |
| **⚙️ Настройки** | Название студии, телефон, адрес, Instagram, Telegram тренера, локации, тренеры, цены |

---

## 🎫 Абонементы

| Тариф | Занятий | Срок | Цена (по умолчанию) |
|-------|---------|------|---------------------|
| Pack 4 | 4 | 30 дней | 500 000 сум |
| Pack 8 | 8 | 30 дней | 800 000 сум |
| Pack 12 🔥 | 12 | 30 дней | 1 100 000 сум |
| Pack 16 💎 | 16 | 30 дней | 1 400 000 сум |

Цены меняются через `.env` без перезборки образа.

---

## 🚀 Деплой на VPS

### Требования
- Ubuntu 22.04 LTS, 1 CPU / 1 GB RAM
- Публичный IP и домен с A-записью → `WEBHOOK_HOST`

### Быстрый деплой (с нуля)
```bash
# На сервере от root:
export DOMAIN=pilates.yourdomain.uz
export CERTBOT_EMAIL=admin@yourdomain.uz
git clone https://github.com/your-org/pilates-bot.git /opt/pilates-bot
bash /opt/pilates-bot/scripts/deploy.sh
```

Скрипт сам: установит Docker + Nginx, получит SSL, создаст `.env` (если нет), поднимет контейнеры, применит миграции.

### Обновление кода
```bash
cd /opt/pilates-bot
git pull
docker compose up -d --build bot webhook
docker compose exec bot alembic upgrade head
```

### Управление
```bash
docker compose logs -f bot           # Логи бота
docker compose logs -f webhook       # Логи webhook/miniapp API
docker compose restart bot           # Рестарт бота
docker compose ps                    # Статус контейнеров
```

---

## 🏃 Локальная разработка

```bash
# 1. Зависимости
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. PostgreSQL + Redis
docker run -d --name pg -e POSTGRES_USER=pilates -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=pilates_db -p 5432:5432 postgres:16-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 3. .env
cp .env.example .env && nano .env

# 4. Миграции
alembic upgrade head

# 5. Бот
python main.py

# 6. Webhook + miniapp API (в другом терминале)
python webhook_runner.py
```

Для теста Payme webhook локально — используй [ngrok](https://ngrok.com):
```bash
ngrok http 8081
# Скопируй URL → вставь в WEBHOOK_HOST
# И укажи в кабинете Payme: https://xxx.ngrok.io/payme/webhook
```

---

## 🗄 База данных

```
users          — клиенты Telegram
  ├── bookings      — записи на занятия  ←→ classes (расписание)
  ├── subscriptions — абонементы (pack_4 / pack_8 / pack_12 / pack_16)
  └── payments      — история платежей Payme
```

```bash
alembic upgrade head       # Применить все миграции
alembic downgrade -1       # Откатить последнюю
alembic revision --autogenerate -m "add X"  # Создать новую
```

---

## 📦 Стек

| Компонент | Технология |
|-----------|-----------|
| Бот | aiogram 3.x (async) |
| База данных | PostgreSQL 16 + SQLAlchemy 2 (asyncpg) |
| FSM-хранилище | Redis |
| Платежи | Payme Business (Subscribe API) |
| MiniApp backend | FastAPI + uvicorn |
| Webhook-сервер | aiohttp |
| Планировщик | APScheduler 3 |
| Миграции | Alembic |
| Деплой | Docker Compose + Nginx + Let's Encrypt |

---

## ❓ Частые вопросы

**Как протестировать оплату?**
Используй TEST-ключи из кабинета Payme. Тестовая карта Uzcard: `8600 4954 7331 6478`.

**Webhook Payme не приходит?**
1. Проверь URL в кабинете Payme (логин `Paycom`, пароль = `PAYME_SECRET_KEY`)
2. Проверь доступность: `curl -I https://yourdomain.uz/payme/webhook`
3. Логи: `docker compose logs webhook`

**Как изменить цены?**
Обнови `PRICE_*` в `.env` и перезапусти бот: `docker compose restart bot`.

**Как добавить тренера или локацию?**
`/admin` → ⚙️ Настройки → поля "Тренеры" и "Студии/локации" (через `|`).

**Telegram тренера для индивидуальных занятий?**
`/admin` → ⚙️ Настройки → "Telegram тренера (@username)".

**Бот не поднимается после рестарта сервера?**
`systemctl enable docker` — контейнеры с `restart: always` стартуют автоматически.
