#!/bin/bash
# =============================================================
# deploy.sh — Деплой бота пилатеса на чистый VPS (Ubuntu 22+)
# =============================================================
# Запуск: bash deploy.sh
# =============================================================
set -euo pipefail

DOMAIN="${DOMAIN:-studio.yourdomain.uz}"
REPO_DIR="/opt/studio-booking-bot"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-admin@yourdomain.uz}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# ─── 1. Зависимости системы ────────────────────────────────────
info "Обновляем пакеты и ставим Docker + fail2ban..."
apt-get update -qq
apt-get install -y -qq \
    docker.io docker-compose-v2 \
    certbot python3-certbot-nginx \
    nginx git curl ufw \
    fail2ban

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
    git clone https://github.com/ushumitsu-bit/studio-booking-bot.git "$REPO_DIR"
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
sed -i "s/pilates\.fapass\.xyz/$DOMAIN/g" "$REPO_DIR/nginx.conf"

# ─── 7. fail2ban ──────────────────────────────────────────────
info "Настраиваем fail2ban..."
mkdir -p /var/log/nginx

# Копируем конфиги
cp "$REPO_DIR/scripts/fail2ban/jail.local"    /etc/fail2ban/jail.local
cp "$REPO_DIR/scripts/fail2ban/nginx-4xx.conf" /etc/fail2ban/filter.d/nginx-4xx.conf

# nginx-limit-req уже есть в стандартной поставке fail2ban
systemctl enable --now fail2ban
systemctl restart fail2ban
info "fail2ban запущен ✓"

# ─── 8. Запуск через Docker Compose ───────────────────────────
info "Собираем и запускаем контейнеры..."
docker compose build --no-cache
docker compose up -d

# ─── 9. Миграции ──────────────────────────────────────────────
info "Ждём запуска PostgreSQL..."
sleep 5
docker compose exec -T bot alembic upgrade head
info "Миграции применены ✓"

# ─── 10. Проверка ─────────────────────────────────────────────
info "Статус контейнеров:"
docker compose ps

info "Статус fail2ban:"
fail2ban-client status

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
║                                                      ║
║  fail2ban:  fail2ban-client status                   ║
║  Забанены:  fail2ban-client status nginx-4xx         ║
║  Разбанить: fail2ban-client unban <IP>               ║
╚══════════════════════════════════════════════════════╝
"
