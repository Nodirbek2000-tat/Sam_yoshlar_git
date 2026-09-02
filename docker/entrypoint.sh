#!/bin/sh
set -e

echo "→ Baza kutilmoqda..."
python - <<'PY'
import os, time, socket

host = os.environ.get('DB_HOST', 'db')
port = int(os.environ.get('DB_PORT', 5432))

for attempt in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"   baza tayyor ({host}:{port})")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"Baza {host}:{port} ga ulanib bo'lmadi")
PY

echo "→ Migratsiyalar..."
python manage.py migrate --noinput

echo "→ Statik fayllar..."
python manage.py collectstatic --noinput --clear

echo "→ Ishga tushmoqda..."
exec "$@"
