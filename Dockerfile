# sam-yosh tadbirkor.uz — Django ilovasi
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Psycopg va Pillow uchun kerakli kutubxonalar
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install gunicorn==23.0.0 whitenoise==6.8.2

COPY . .

RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
# Worker soni yadroga qarab: (yadro × 2) + 1. 4 yadroli serverda — 9 ta.
# Har biri 2 ta ip bilan: bir vaqtda ~18 so'rov. `--max-requests` — worker
# vaqti-vaqti bilan yangilanadi, xotira sekin o'sib ketmasin.
CMD ["sh", "-c", "gunicorn config.wsgi:application \
     --bind 0.0.0.0:8000 \
     --worker-class gthread \
     --workers ${GUNICORN_WORKERS:-9} \
     --threads ${GUNICORN_THREADS:-2} \
     --timeout 120 \
     --graceful-timeout 30 \
     --max-requests 1200 \
     --max-requests-jitter 200 \
     --access-logfile - \
     --error-logfile -"]
