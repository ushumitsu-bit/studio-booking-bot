# 🧘 Pilates Bot — Telegram-бот для записи на пилатес

Полноценный бот для управления студией пилатеса:
запись клиентов, расписание, оплата через **ЮKassa**, напоминания и "пинки" за пропуски.

---

## 🗂 Структура проекта

```
pilates_bot/
├── main.py                    # Точка входа — запуск бота
├── webhook_app.py             # aiohttp-сервер для webhook ЮKassa
├── config.py                  # Настройки (pydantic-settings + .env)
│
├── bot/
│   ├── handlers/
│   │   ├── client.py          # /start, расписание, запись, абонемент
│   │   ├── admin.py           # Панель администратора
│   │   └── payments.py        # Оплата + webhook ЮKassa
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
│   ├── yukassa.py             # Интеграция с ЮKassa API
│   └── scheduler.py          # APScheduler: напоминания, пинки, реактивация
│
├── migrations/                # Alembic-миграции
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py     # Создание всех таблиц
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

# ЮKassa — личный кабинет: https://yookassa.ru/my/merchant/integration
YUKASSA_SHOP_ID=123456
YUKASSA_SECRET_KEY=test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
YUKASSA_RETURN_URL=https://t.me/your_pilates_bot

# Домен для webhook (нужен HTTPS)
WEBHOOK_HOST=https://pilates.yourdomain.ru
WEBHOOK_PATH=/yukassa/webhook

# Цены в рублях
PRICE_SINGLE=1200
PRICE_4_CLASSES=4200
PRICE_8_CLASSES=6400
```

---

## 🏦 Настройка ЮKassa (пошагово)

### 1. Регистрация
Зайди на [yookassa.ru](https://yookassa.ru) → создай магазин → пройди верификацию.

### 2. Получи ключи
Личный кабинет → **Интеграция** → **API-ключи**:
- `shopId` → `YUKASSA_SHOP_ID`
- Секретный ключ → `YUKASSA_SECRET_KEY`

> **Тестирование:** используй ключ вида `test_xxx...`  
> Тестовая карта: `5555 5555 5555 4444`, любой CVV, дата в будущем

### 3. Настрой webhook
Личный кабинет → **Интеграция** → **HTTP-уведомления**:
- URL: `https://pilates.yourdomain.ru/yukassa/webhook`
- События: ✅ `payment.succeeded`

### 4. Как работает оплата

```
Клиент → /pay → выбирает тариф
  ↓
Бот создаёт Payment в БД + запрос в ЮKassa API
  ↓
ЮKassa возвращает payment_url
  ↓
Бот отправляет кнопку "Перейти к оплате"
  ↓
Клиент платит (карта / СБП / ЮMoney)
  ↓
ЮKassa POST /yukassa/webhook → {event: "payment.succeeded"}
  ↓
Бот: confirm_payment() → активирует абонемент
  ↓
Клиент получает сообщение "Оплата прошла! 🎉"
```

---

## 🔔 Автоматические напоминания (scheduler.py)

| Триггер | Когда | Действие |
|---------|-------|---------|
| Напоминание 24ч | За 24 часа до занятия | Сообщение с кнопками «Приду» / «Отменить» |
| Напоминание 2ч  | За 2 часа до занятия  | Лёгкое напоминание |
| **Пинок** | Через ~2ч после занятия, клиент не пришёл | «Ты не пришла... всё ок?» |
| Абонемент | За 3 дня до истечения | «Продли, чтобы не потерять место» |
| Реактивация | 14+ дней без занятий | «Скучаем, возвращайся!» |

Все задачи запускаются через **APScheduler** в фоне того же процесса что и бот.

---

## 🚀 Запуск локально (для разработки)

### 1. Установи зависимости
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Подними PostgreSQL и Redis
```bash
docker run -d --name pilates-pg \
  -e POSTGRES_USER=pilates \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=pilates_db \
  -p 5432:5432 postgres:16-alpine

docker run -d --name pilates-redis \
  -p 6379:6379 redis:7-alpine
```

### 3. Применить миграции
```bash
alembic upgrade head
```

### 4. Запустить бота
```bash
python main.py
```

### 5. Webhook ЮKassa (локально)
Для теста webhook используй [ngrok](https://ngrok.com):
```bash
ngrok http 8080
# Скопируй https://xxx.ngrok.io → вставь в WEBHOOK_HOST в .env
# И в личный кабинет ЮKassa
```

Запусти webhook-сервер отдельно:
```bash
python -c "
import asyncio
from aiogram import Bot
from config import settings
from webhook_app import run_webhook_server
bot = Bot(token=settings.BOT_TOKEN)
asyncio.run(run_webhook_server(bot))
asyncio.get_event_loop().run_forever()
"
```

---

## 🐳 Деплой на VPS (production)

### Требования к серверу
- Ubuntu 22.04 LTS
- 1 CPU / 1 GB RAM (минимум)
- Публичный IP и домен с A-записью

### Быстрый деплой
```bash
# На сервере:
export DOMAIN=pilates.yourdomain.ru
export CERTBOT_EMAIL=admin@yourdomain.ru
bash <(curl -s https://raw.githubusercontent.com/your-org/pilates_bot/main/scripts/deploy.sh)
```

Или вручную:
```bash
git clone https://github.com/your-org/pilates_bot.git /opt/pilates_bot
cd /opt/pilates_bot
cp .env.example .env
nano .env                        # Заполни все переменные
docker compose up -d --build
docker compose exec bot alembic upgrade head
```

### Управление
```bash
docker compose logs -f bot       # Логи в реальном времени
docker compose restart bot       # Рестарт бота
docker compose down              # Остановить всё
docker compose ps                # Статус контейнеров
```

### Обновление кода
```bash
cd /opt/pilates_bot
git pull
docker compose up -d --build bot
docker compose exec bot alembic upgrade head
```

---

## 👩‍💼 Команды администратора

| Команда | Описание |
|---------|---------|
| `/admin` | Открыть панель администратора |
| **➕ Добавить занятие** | FSM-диалог: название → тренер → дата/время → мест |
| **👥 Клиенты с долгами** | Список клиентов без активного абонемента |
| **📣 Рассылка** | Отправить HTML-сообщение всем клиентам |

Чтобы стать администратором — добавь свой Telegram ID в `ADMIN_IDS` в `.env`.  
Узнать свой ID: напиши боту [@userinfobot](https://t.me/userinfobot).

---

## 🗄 База данных (схема)

```
users          — клиенты Telegram
  └── bookings      — записи на занятия  ←→ classes (расписание)
  └── subscriptions — абонементы
  └── payments      — история платежей ЮKassa
```

Управление миграциями:
```bash
# Создать новую миграцию
alembic revision --autogenerate -m "add column X"

# Применить
alembic upgrade head

# Откатить
alembic downgrade -1
```

---

## 📦 Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Бот | aiogram 3.7 (async) |
| База данных | PostgreSQL 16 + SQLAlchemy 2 (asyncpg) |
| FSM-хранилище | Redis |
| Платежи | ЮKassa (официальный SDK) |
| Webhook-сервер | aiohttp |
| Планировщик | APScheduler 3 |
| Миграции | Alembic |
| Деплой | Docker Compose + Nginx + Let's Encrypt |

---

## ❓ Частые вопросы

**Как протестировать оплату без реальных денег?**  
Используй тестовый секретный ключ из ЮKassa (`test_xxx`).  
Тестовые карты: [yookassa.ru/developers/payment-acceptance/testing](https://yookassa.ru/developers/payment-acceptance/testing)

**Webhook ЮKassa не приходит?**  
1. Проверь что URL прописан в кабинете ЮKassa
2. Убедись что домен доступен из интернета: `curl -I https://yourdomain.ru/yukassa/webhook`
3. Проверь логи: `docker compose logs webhook`

**Как добавить нового тренера или изменить цены?**  
Измени в `.env` переменные `PRICE_*` и перезапусти бота.

**Бот не отвечает после рестарта сервера?**  
Убедись что Docker настроен на автозапуск: `systemctl enable docker`  
Контейнеры с `restart: always` поднимутся автоматически.
"# pilates-bot"  
