#!/bin/bash
# =============================================================
# deploy.sh — Деплой бота пилатеса на чистый VPS (Ubuntu 22+)
# =============================================================
# Запуск: bash deploy.sh
# =============================================================
set -euo pipefail

DOMAIN="${DOMAIN:-pilates.yourdomain.ru}"
REPO_DIR="/opt/pilates_bot"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-admin@yourdomain.ru}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# ─── 1. Зависимости системы ────────────────────────────────────
info "Обновляем пакеты и ставим Docker..."
apt-get update -qq
apt-get install -y -qq \
    docker.io docker-compose-v2 \
    certbot python3-certbot-nginx \
    nginx git curl ufw

systemctl enable --now docker

# ─── 2. Firewall ───────────────────────────────────────────────
info "Настраиваем UFW..."
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP  (Let's Encrypt + redirect)
ufw allow 443/tcp   # HTTPS
ufw --force enable

# ─── 3. Код ────────────────────────────────────────────────────
info "Клонируем / обновляем репозиторий..."
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull
else
    # Замените URL на ваш репозиторий
    git clone https://github.com/your-org/pilates_bot.git "$REPO_DIR"
fi

cd "$REPO_DIR"

# ─── 4. .env ───────────────────────────────────────────────────
if [ ! -f .env ]; then
    warn ".env не найден! Копируем шаблон..."
    cp .env.example .env
    warn "ВАЖНО: отредактируй .env перед запуском: nano $REPO_DIR/.env"
    exit 1
fi

# ─── 5. SSL-сертификат ─────────────────────────────────────────
info "Получаем SSL-сертификат для $DOMAIN..."
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    certbot certonly --nginx \
        -d "$DOMAIN" \
        --non-interactive \
        --agree-tos \
        --email "$CERTBOT_EMAIL"
fi

# Автопродление в cron
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && docker compose -f $REPO_DIR/docker-compose.yml exec -T nginx nginx -s reload") | crontab -

# ─── 6. nginx.conf — подставляем домен ────────────────────────
info "Настраиваем nginx с доменом $DOMAIN..."
sed -i "s/pilates.yourdomain.ru/$DOMAIN/g" "$REPO_DIR/nginx.conf"

# ─── 7. Запуск через Docker Compose ───────────────────────────
info "Собираем и запускаем контейнеры..."
docker compose build --no-cache
docker compose up -d

# ─── 8. Миграции ──────────────────────────────────────────────
info "Ждём запуска PostgreSQL..."
sleep 5
docker compose exec -T bot alembic upgrade head
info "Миграции применены ✓"

# ─── 9. Проверка ──────────────────────────────────────────────
info "Статус контейнеров:"
docker compose ps

info "
╔══════════════════════════════════════════════════════╗
║  Деплой завершён!                                    ║
╠══════════════════════════════════════════════════════╣
║  Бот запущен                                         ║
║  Payme webhook:  https://$DOMAIN/payme/webhook       ║
║  Miniapp:        https://$DOMAIN/miniapp/            ║
║                                                      ║
║  Логи:    docker compose logs -f bot                 ║
║  Стоп:    docker compose down                        ║
║  Рестарт: docker compose restart bot                 ║
╚══════════════════════════════════════════════════════╝
"
