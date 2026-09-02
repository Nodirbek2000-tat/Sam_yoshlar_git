# Serverga qo'yish — samyosh.uz

Docker + nginx + PostgreSQL + avtomatik SSL (Let's Encrypt).

## Nima bor

| Xizmat | Vazifasi |
|---|---|
| `db` | PostgreSQL 16 — ma'lumotlar **nomli volume**da, konteyner o'chsa ham saqlanadi |
| `web` | Django + gunicorn (3 worker) |
| `nginx` | 80 → 443 yo'naltirish, statik/media fayllar, proxy |
| `certbot` | SSL sertifikat — har 12 soatda tekshiradi va **o'zi yangilaydi** |
| `bot` | Telegram bot (ixtiyoriy profil) |

## 1. Tayyorgarlik

Serverda Docker va Docker Compose bo'lishi kerak:

```bash
curl -fsSL https://get.docker.com | sh
```

Domen **samyosh.uz** va **www.samyosh.uz** server IP manziliga
(`A` yozuv) yo'naltirilgan bo'lsin. Bu shart — certbot shuni tekshiradi.

## 2. Sozlash

```bash
cd /srv/samyosh
cp .env.production.example .env
nano .env
```

Albatta o'zgartiring:

- `SECRET_KEY` — uzun tasodifiy qator
- `DB_PASSWORD` — kuchli parol
- `TELEGRAM_API_SECRET` — bot `.env` dagi `API_SECRET` bilan **bir xil**

Kalit yaratish:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 3. Birinchi ishga tushirish + SSL

```bash
./docker/init-ssl.sh sizning@email.uz
```

Skript o'zi:
1. Vaqtinchalik nginx ni (faqat 80-port) ko'taradi
2. Let's Encrypt dan sertifikat oladi
3. To'liq HTTPS konfiguratsiyaga o'tadi
4. Hamma xizmatlarni ishga tushiradi

Tayyor: **https://samyosh.uz**

## 4. Admin yaratish

```bash
docker compose exec web python manage.py createsuperuser
```

Boshlang'ich ma'lumot (ixtiyoriy):

```bash
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py seed_initiatives
```

## 5. Botni ishga tushirish

Bot ham Docker'da tayyor. `E:\Sma_yoshlar_bot\.env` (serverda `../Sma_yoshlar_bot/.env`):

```
BOT_TOKEN=BotFather bergan token
ADMINS=telegram_id
ip=localhost

SITE_URL=https://samyosh.uz
API_SECRET=<Django .env dagi TELEGRAM_API_SECRET bilan bir xil>
```

Ishga tushirish:

```bash
docker compose --profile bot up -d bot
docker compose logs -f bot
```

> Bot papkasi Django loyihasining **yonida** turishi kerak:
> ```
> /srv/
>   ├── Sam_yoshlar/          ← Django (docker-compose shu yerda)
>   └── Sma_yoshlar_bot/      ← bot
>       ├── .env
>       └── sam_yoshlar_bot/  ← Dockerfile shu yerda
> ```

## Kundalik amallar

```bash
# Holat
docker compose ps

# Loglar
docker compose logs -f web
docker compose logs -f nginx

# Yangilanish chiqarish
git pull
docker compose build web
docker compose up -d web

# Qayta ishga tushirish
docker compose restart web
```

## Baza — eng muhimi

Ma'lumotlar `postgres_data` nomli volume'da. **`docker compose down` baza volume'ini
o'chirmaydi** — konteynerlar o'chadi, ma'lumot qoladi.

> ⚠️ `docker compose down -v` ni **hech qachon** ishlatmang — `-v` volume'larni,
> ya'ni butun bazani o'chiradi.

### Zaxira nusxa

```bash
# Saqlash
docker compose exec -T db pg_dump -U samyosh samyosh > zaxira-$(date +%F).sql

# Tiklash
cat zaxira-2026-09-02.sql | docker compose exec -T db psql -U samyosh samyosh
```

Har kuni avtomatik saqlash uchun cron:

```bash
0 3 * * * cd /srv/samyosh && docker compose exec -T db pg_dump -U samyosh samyosh | gzip > /srv/backups/samyosh-$(date +\%F).sql.gz
```

### Media fayllar

Rasm va hujjatlar `media_files` volume'ida:

```bash
docker run --rm -v samyosh_media_files:/data -v $(pwd):/backup alpine \
    tar czf /backup/media-$(date +%F).tar.gz -C /data .
```

## SSL yangilanishi

`certbot` konteyneri har 12 soatda `certbot renew` ishlatadi — muddati 30 kundan
kam qolganda o'zi yangilaydi. `nginx` ham har 12 soatda konfiguratsiyani qayta
yuklaydi, ya'ni yangi sertifikat o'zi qo'llanadi. **Qo'lda hech narsa qilish shart emas.**

Tekshirish:

```bash
docker compose run --rm certbot certificates
```

## Muammo bo'lsa

| Belgi | Sabab / yechim |
|---|---|
| certbot xato beradi | Domen server IP ga yo'naltirilmagan, yoki 80-port band |
| 502 Bad Gateway | `web` ko'tarilmagan — `docker compose logs web` |
| Statik fayllar yo'q | `docker compose exec web python manage.py collectstatic --noinput` |
| Bot javob bermaydi | `API_SECRET` ikkala `.env` da bir xilmi? `SITE_URL` to'g'rimi? |
