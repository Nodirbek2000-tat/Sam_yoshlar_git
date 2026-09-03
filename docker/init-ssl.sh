#!/bin/sh
# Birinchi marta SSL sertifikat olish (keyin certbot o'zi yangilab turadi).
#
# Ishlatish:  ./docker/init-ssl.sh sizning@email.uz
set -e

DOMAIN="${DOMAIN:-mentadbirkor.uz}"
EMAIL="${1:-}"

if [ -z "$EMAIL" ]; then
    echo "Email ko'rsating:  ./docker/init-ssl.sh sizning@email.uz"
    exit 1
fi

# Xato bo'lsa ham konfiguratsiya yarim holatda qolib ketmasin
restore() {
    [ -f docker/nginx/samyosh-initial.conf ] &&         mv docker/nginx/samyosh-initial.conf docker/nginx/samyosh-initial.conf.disabled
    [ -f docker/nginx/samyosh.conf.off ] &&         mv docker/nginx/samyosh.conf.off docker/nginx/samyosh.conf
    return 0
}

fail() {
    echo ""
    echo "XATO: sertifikat olinmadi."
    echo "Tekshiring:  dig +short $DOMAIN   ->  server IP bilan bir xil bo'lishi kerak"
    restore
    docker compose up -d nginx >/dev/null 2>&1 || true
    exit 1
}

trap fail INT TERM

echo "→ 1/3  Vaqtinchalik nginx (faqat 80-port) ishga tushirilmoqda..."
mv docker/nginx/samyosh.conf docker/nginx/samyosh.conf.off 2>/dev/null || true
mv docker/nginx/samyosh-initial.conf.disabled docker/nginx/samyosh-initial.conf 2>/dev/null || true

docker compose up -d web nginx
sleep 5

echo "→ 2/3  Sertifikat olinmoqda ($DOMAIN)..."
docker compose run --rm certbot certonly \
    --webroot -w /var/www/certbot \
    -d "$DOMAIN" -d "www.$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos --no-eff-email \
    --non-interactive || fail

echo "→ 3/3  To'liq konfiguratsiyaga qaytilmoqda..."
trap - INT TERM
restore

docker compose up -d

echo ""
echo "Tayyor. https://$DOMAIN"
echo "Sertifikat har 12 soatda tekshiriladi va muddati yaqinlashsa avtomatik yangilanadi."
