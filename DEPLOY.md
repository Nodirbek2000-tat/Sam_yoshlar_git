# Serverga qo'yish — samarqandyoshlari.uz

Docker + nginx + PostgreSQL + Next.js + avtomatik SSL.

## Tuzilishi

```
                    ┌─────────── nginx (80 / 443) ───────────┐
                    │  HTTPS shu yerda tugaydi               │
                    └───┬──────────────┬─────────────┬───────┘
                        │              │             │
                   /    │        /api/ │  /static/   │ /media/
                        ▼              ▼             ▼
                 ┌──────────┐   ┌──────────┐   ┌──────────┐
                 │  front   │   │   web    │   │  fayllar │
                 │ Next.js  │   │  Django  │   │ (volume) │
                 │  :3000   │   │  :8000   │   └──────────┘
                 └──────────┘   └────┬─────┘
                                     ▼
                                ┌─────────┐
                                │   db    │  PostgreSQL
                                └─────────┘
```

| Xizmat | Vazifasi |
|---|---|
| `db` | PostgreSQL 16 — ma'lumotlar **nomli volume**da, konteyner o'chsa ham qoladi |
| `web` | Django: REST API (`/api/v1/`) va admin (`/boshqaruv/`) |
| `front` | Next.js — foydalanuvchi ko'radigan sayt |
| `nginx` | ikkalasining oldida turadi, 80 → 443 yo'naltiradi, fayllarni o'zi beradi |
| `certbot` | SSL sertifikat — har 12 soatda tekshiradi va **o'zi yangilaydi** |
| `bot` | Telegram bot (`--profile bot`) |

> **nginx frontning ichida emas.** U alohida konteyner bo'lib, so'rovni manzilga
> qarab frontga yoki Django'ga uzatadi.

## Papkalar

Serverda uchala loyiha yonma-yon tursin:

```
~/
├── Sam_yoshlar_git/          ← Django (docker-compose shu yerda)
└── Sma_yoshlar_bot/
    ├── sam_yoshlar_front/    ← Next.js
    └── sam_yoshlar_bot/      ← Telegram bot
```

Boshqacha joylashtirsangiz `.env` da `FRONT_PATH` va `BOT_PATH` ni ko'rsating.

---

## 1. Tayyorgarlik

Docker bo'lishi kerak:

```bash
curl -fsSL https://get.docker.com | sh
```

DNS: **samarqandyoshlari.uz** va **www.samarqandyoshlari.uz** server IP manziliga `A` yozuv
bilan yo'naltirilgan bo'lsin. Bu shart — certbot shuni tekshiradi.

```bash
dig +short samarqandyoshlari.uz @8.8.8.8
```

## 2. Sozlash

```bash
cd ~/Sam_yoshlar_git
cp .env.production.example .env
nano .env
```

Albatta o'zgartiring:

- `SECRET_KEY` — uzun tasodifiy qator
- `DB_PASSWORD` — kuchli parol
- `TELEGRAM_API_SECRET` — bot `.env` dagi `API_SECRET` bilan **bir xil**

Kalit yaratish:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 3. Birinchi ishga tushirish + SSL

```bash
./docker/init-ssl.sh sizning@email.uz
```

Skript o'zi:

1. Vaqtinchalik nginx ni (faqat 80-port) ko'taradi
2. Let's Encrypt dan sertifikat oladi
3. To'liq HTTPS konfiguratsiyaga o'tadi
4. Hamma xizmatni ishga tushiradi

Tayyor: **https://samarqandyoshlari.uz**

## 4. Admin va boshlang'ich ma'lumot

```bash
docker compose exec web python manage.py createsuperuser
```

Ixtiyoriy:

```bash
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py seed_initiatives
```

## 5. Botni ishga tushirish

`~/Sma_yoshlar_bot/sam_yoshlar_bot/.env`:

```
BOT_TOKEN=BotFather bergan token
ADMINS=telegram_id
SITE_URL=https://samarqandyoshlari.uz
API_SECRET=<Django .env dagi TELEGRAM_API_SECRET bilan bir xil>
```

```bash
docker compose --profile bot up -d bot
docker compose logs -f bot
```

---

## Yangilanish chiqarish

```bash
./deploy.sh          # backend + frontend
./deploy.sh front    # faqat frontend
./deploy.sh back     # faqat backend
```

Skript: kodni tortadi → obrazlarni quradi → migratsiya qiladi →
statik fayllarni yig'adi → xizmatlarni almashtiradi → eski obrazlarni tozalaydi.

**Baza va media fayllarga tegilmaydi.** Skript hech qachon `down -v` ishlatmaydi.

> ⚠️ `docker compose down -v` ni **hech qachon** qo'lda ishlatmang —
> `-v` volume'larni, ya'ni butun bazani o'chiradi.

### Frontend `NEXT_PUBLIC_API_URL` haqida

Bu qiymat **qurish paytida** kodga yoziladi, ishga tushirishda emas.
Domenni o'zgartirsangiz `.env` dagi `PUBLIC_API_URL` ni yangilab,
frontni **qayta build** qiling:

```bash
docker compose build front && docker compose up -d front
```

---

## Baza — eng muhimi

### Zaxira nusxa

```bash
docker compose exec -T db pg_dump -U samyosh samyosh > ~/zaxira-$(date +%F).sql
```

Tiklash:

```bash
cat ~/zaxira-2026-09-08.sql | docker compose exec -T db psql -U samyosh samyosh
```

Har kuni avtomatik (cron):

```bash
0 3 * * * cd ~/Sam_yoshlar_git && docker compose exec -T db pg_dump -U samyosh samyosh | gzip > ~/backups/samyosh-$(date +\%F).sql.gz
```

### Media fayllar

```bash
docker run --rm -v sam_yoshlar_git_media_files:/data -v $(pwd):/backup alpine \
    tar czf /backup/media-$(date +%F).tar.gz -C /data .
```

---

## SSL yangilanishi

`certbot` har 12 soatda `certbot renew` ishlatadi — muddati 30 kundan kam
qolganda o'zi yangilaydi. `nginx` ham har 12 soatda konfiguratsiyani qayta
yuklaydi, ya'ni yangi sertifikat o'zi qo'llanadi. **Qo'lda hech narsa qilish shart emas.**

Tekshirish:

```bash
docker compose run --rm --entrypoint certbot certbot certificates
```

---

## Kundalik amallar

```bash
docker compose ps                  # holat
docker compose logs -f front       # frontend loglari
docker compose logs -f web         # Django loglari
docker compose logs -f nginx
docker compose restart front
```

## Muammo bo'lsa

| Belgi | Sabab / yechim |
|---|---|
| certbot xato beradi | Domen server IP ga yo'naltirilmagan, yoki 80-port band |
| 502 Bad Gateway | `front` yoki `web` ko'tarilmagan — `docker compose logs` |
| nginx `Restarting` siklida | Konfigda eski domen yoki yo'q sertifikat — `docker compose logs nginx` aniq faylni ko'rsatadi |
| Frontend eski API ga uradi | `PUBLIC_API_URL` o'zgargan, lekin front qayta build qilinmagan |
| Django statik fayllari yo'q | `docker compose exec web python manage.py collectstatic --noinput` |
| Bot javob bermaydi | `API_SECRET` ikkala `.env` da bir xilmi? `SITE_URL` to'g'rimi? |
