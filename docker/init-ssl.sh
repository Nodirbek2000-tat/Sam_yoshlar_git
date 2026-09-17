#!/bin/sh
# Birinchi marta SSL sertifikat olish. Keyin certbot o'zi yangilab turadi.
#
# Ishlatish:  ./docker/init-ssl.sh sizning@email.uz
set -e

DOMAIN="${DOMAIN:-samarqandyoshlari.uz}"
EMAIL="${1:-}"

CONF_DIR="docker/nginx"
LIVE="$CONF_DIR/site.conf"
INITIAL="$CONF_DIR/site-initial.conf"

if [ -z "$EMAIL" ]; then
    echo "Email ko'rsating:  ./docker/init-ssl.sh sizning@email.uz"
    exit 1
fi

# Xato bo'lsa konfiguratsiya yarim holatda qolib ketmasin
restore() {
    [ -f "$INITIAL" ] && mv "$INITIAL" "$INITIAL.disabled"
    [ -f "$LIVE.off" ] && mv "$LIVE.off" "$LIVE"
    return 0
}

fail() {
    echo ""
    echo "XATO: sertifikat olinmadi."
    echo "Tekshiring:  dig +short $DOMAIN   ->  server IP bilan bir xil bo'lishi kerak"
    restore
    docker compose restart nginx >/dev/null 2>&1 || true
    exit 1
}

trap fail INT TERM

echo "-> 1/3  Vaqtinchalik nginx (faqat 80-port) ishga tushirilmoqda..."
mv "$LIVE" "$LIVE.off" 2>/dev/null || true
mv "$INITIAL.disabled" "$INITIAL" 2>/dev/null || true

docker compose up -d web front nginx
# nginx ishlab turgan bo'lsa ham yangi konfigni o'qishi shart
docker compose restart nginx
sleep 5

echo "-> 2/3  Sertifikat olinmoqda ($DOMAIN)..."
# `--entrypoint` shart: servisning o'z entrypoint'i cheksiz `renew` sikli,
# usiz bu buyruq e'tiborsiz qoladi va konteyner qotib qoladi.
docker compose run --rm --entrypoint certbot certbot certonly \
    --webroot -w /var/www/certbot \
    -d "$DOMAIN" -d "www.$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos --no-eff-email \
    --non-interactive || fail

echo "-> 3/3  To'liq HTTPS konfiguratsiyaga qaytilmoqda..."
trap - INT TERM
restore

docker compose up -d
docker compose restart nginx

echo ""
echo "Tayyor. https://$DOMAIN"
echo "Sertifikat har 12 soatda tekshiriladi va muddati yaqinlashsa avtomatik yangilanadi."
