#!/bin/sh
# Yangilanishni chiqarish: kod tortiladi, obrazlar qayta quriladi, xizmatlar almashadi.
#
# Baza va yuklangan fayllar TEGILMAYDI — ular nomli volume'da yotadi va
# bu skript hech qachon `down -v` ishlatmaydi.
#
# Ishlatish:
#     ./deploy.sh            # backend + frontend
#     ./deploy.sh front      # faqat frontend
#     ./deploy.sh back       # faqat backend
set -e

TARGET="${1:-all}"
FRONT_PATH="${FRONT_PATH:-../Sma_yoshlar_bot/sam_yoshlar_front}"

say() {
    echo ""
    echo "==> $1"
}

# --- 1. Kodni tortamiz ---

if [ "$TARGET" = "all" ] || [ "$TARGET" = "back" ]; then
    say "Backend kodi tortilmoqda"
    git pull --ff-only
fi

if [ "$TARGET" = "all" ] || [ "$TARGET" = "front" ]; then
    if [ -d "$FRONT_PATH/.git" ]; then
        say "Frontend kodi tortilmoqda"
        git -C "$FRONT_PATH" pull --ff-only
    else
        say "Frontend papkasi git repo emas — o'tkazib yuborildi ($FRONT_PATH)"
    fi
fi

# --- 2. Obrazlarni quramiz ---

case "$TARGET" in
    front) SERVICES="front" ;;
    back)  SERVICES="web" ;;
    *)     SERVICES="web front" ;;
esac

say "Obrazlar qurilmoqda: $SERVICES"
# shellcheck disable=SC2086
docker compose build $SERVICES

# --- 3. Migratsiya (baza tuzilmasi o'zgargan bo'lsa) ---

if [ "$TARGET" = "all" ] || [ "$TARGET" = "back" ]; then
    say "Baza migratsiyalari"
    docker compose run --rm web python manage.py migrate --noinput

    say "Statik fayllar yig'ilmoqda"
    docker compose run --rm web python manage.py collectstatic --noinput
fi

# --- 4. Xizmatlarni almashtiramiz ---

say "Xizmatlar ishga tushirilmoqda"
# shellcheck disable=SC2086
docker compose up -d --no-deps $SERVICES
docker compose up -d nginx certbot

# --- 5. Eski obrazlarni tozalaymiz ---

say "Ishlatilmayotgan obrazlar tozalanmoqda"
docker image prune -f >/dev/null 2>&1 || true

say "Holat"
docker compose ps

echo ""
echo "Tayyor. Baza va media fayllarga tegilmadi."
