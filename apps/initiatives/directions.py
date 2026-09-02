"""«Yoshlar Ovozi» — 14 ta yo'nalish reyestri.

Har bir yo'nalishning o'z rangi, ikonkasi va tirik sahnasi bor: ovoz qo'shilgan sari
sahna o'sadi (daraxt barg chiqaradi, shahar yonadi, neyronlar ulanadi...).
Sahna chizish mantiqi `static/js/voice.js` ichida — shu yerdagi `scene` kaliti bilan bog'lanadi.
"""

DIRECTIONS = [
    {
        'id': 'eco', 'scene': 'eco',
        'name': "Ekologiya", 'title': "Yoshlar Daraxti",
        'color': '#4CAF7D', 'accent': '#a8e0be',
        'max': 40, 'unit': "barg",
        'tagline': "Toza havo, yashil hudud va chiqindini qayta ishlash g'oyalari.",
        'icon': '<path d="M20 34V18"/><path d="M20 20c-8 0-12-6-12-12 8 0 12 4 12 10z"/>'
                '<path d="M20 16c8 0 12-6 12-12-8 0-12 4-12 10z"/>',
    },
    {
        'id': 'fintech', 'scene': 'fintech',
        'name': "Fintex", 'title': "Kapital Shahri",
        'color': '#d9b36c', 'accent': '#f6e0ab',
        'max': 45, 'unit': "tanga",
        'tagline': "To'lov tizimlari, mikrokredit va moliyaviy savodxonlik yechimlari.",
        'icon': '<circle cx="14" cy="26" r="7"/><circle cx="26" cy="14" r="9"/>'
                '<path d="M23 14h6M26 11v6"/>',
    },
    {
        'id': 'ai', 'scene': 'ai',
        'name': "Sun'iy intellekt", 'title': "Neyron Tarmoq",
        'color': '#6c8cff', 'accent': '#b6c4ff',
        'max': 47, 'unit': "neyron",
        'tagline': "AI, ma'lumotlar tahlili va avtomatlashtirish loyihalari.",
        'icon': '<circle cx="20" cy="20" r="4"/><circle cx="8" cy="10" r="3"/>'
                '<circle cx="32" cy="10" r="3"/><circle cx="8" cy="30" r="3"/>'
                '<circle cx="32" cy="30" r="3"/><path d="M11 12l6 6M29 12l-6 6M11 28l6-6M29 28l-6-6"/>',
    },
    {
        'id': 'edu', 'scene': 'edu',
        'name': "Ta'lim", 'title': "Bilim Kitobi",
        'color': '#e0a83e', 'accent': '#f6d998',
        'max': 22, 'unit': "sahifa",
        'tagline': "Onlayn kurslar, mentorlik va zamonaviy o'qitish usullari.",
        'icon': '<path d="M6 10c6-3 12-3 14 0v20c-2-3-8-3-14 0z"/>'
                '<path d="M34 10c-6-3-12-3-14 0v20c2-3 8-3 14 0z"/>',
    },
    {
        'id': 'social', 'scene': 'social',
        'name': "Ijtimoiy soha", 'title': "Birlik",
        'color': '#e08a6b', 'accent': '#f6c3ac',
        'max': 36, 'unit': "inson",
        'tagline': "Ehtiyojmandlarga yordam, volontyorlik va inklyuziv loyihalar.",
        'icon': '<circle cx="12" cy="12" r="5"/><circle cx="28" cy="12" r="5"/>'
                '<path d="M4 32c1-8 6-11 8-11s3 1 8 1 6-1 8-1 7 3 8 11"/>',
    },
    {
        'id': 'agro', 'scene': 'agro',
        'name': "Agrotexnologiya", 'title': "Urug'dan Hosilgacha",
        'color': '#8bc34a', 'accent': '#c8e6a3',
        'max': 56, 'unit': "urug'",
        'tagline': "Aqlli dehqonchilik, tomchilatib sug'orish va hosil monitoringi.",
        'icon': '<path d="M20 34V18"/><path d="M20 18c0-8-6-12-12-12 0 8 6 12 12 12z"/>'
                '<path d="M20 22c0-6 5-9 9-9 0 6-5 9-9 9z"/>',
    },
    {
        'id': 'energy', 'scene': 'energy',
        'name': "Energetika", 'title': "Quyoshli Qishloq",
        'color': '#f2c14e', 'accent': '#fbe3a0',
        'max': 30, 'unit': "nur",
        'tagline': "Quyosh panellari, energiya tejash va muqobil manbalar.",
        'icon': '<circle cx="20" cy="20" r="6"/>'
                '<path d="M20 4v4M20 32v4M4 20h4M32 20h4M9 9l3 3M28 28l3 3M31 9l-3 3M12 28l-3 3"/>',
    },
    {
        'id': 'industry', 'scene': 'industry',
        'name': "Sanoat", 'title': "Aqlli Zavod",
        'color': '#93a1b5', 'accent': '#cdd6e1',
        'max': 24, 'unit': "blok",
        'tagline': "Ishlab chiqarishni raqamlashtirish va mahalliylashtirish.",
        'icon': '<path d="M6 34V18l8 5v-5l8 5v-5l8 5v11z"/><path d="M6 34h28"/>',
    },
    {
        'id': 'startup', 'scene': 'startup',
        'name': "Startap", 'title': "Kelajakka Uchish",
        'color': '#4fc3d9', 'accent': '#a6e4ef',
        'max': 22, 'unit': "detal",
        'tagline': "Yangi biznes modellari va tez o'sadigan loyihalar.",
        'icon': '<path d="M20 4c6 4 8 12 6 20l-6 4-6-4c-2-8 0-16 6-20z"/>'
                '<path d="M14 24l-6 6M26 24l6 6M17 30l-1 6M23 30l1 6"/>',
    },
    {
        'id': 'creative', 'scene': 'creative',
        'name': "Ijodiy sanoat", 'title': "San'atni Yarat",
        'color': '#c767c2', 'accent': '#eab4e6',
        'max': 64, 'unit': "piksel",
        'tagline': "Dizayn, kino, musiqa va raqamli kontent loyihalari.",
        'icon': '<rect x="6" y="6" width="10" height="10"/><rect x="18" y="6" width="10" height="10"/>'
                '<rect x="6" y="18" width="10" height="10"/><rect x="18" y="18" width="10" height="10"/>',
    },
    {
        'id': 'culture', 'scene': 'culture',
        'name': "Madaniyat", 'title': "Meros",
        'color': '#c9974a', 'accent': '#efcb8e',
        'max': 20, 'unit': "blok",
        'tagline': "Milliy meros, hunarmandchilik va madaniy turizm.",
        'icon': '<path d="M8 34V18L20 8l12 10v16"/><path d="M4 34h32M14 34V22h12v12"/>',
    },
    {
        'id': 'smartcity', 'scene': 'smartcity',
        'name': "Aqlli shahar", 'title': "Shaharni Yoqing",
        'color': '#5c7cfa', 'accent': '#a8bbff',
        'max': 60, 'unit': "chiroq",
        'tagline': "Transport, xavfsizlik va shahar xizmatlarini raqamlashtirish.",
        'icon': '<rect x="6" y="14" width="8" height="20"/><rect x="17" y="6" width="8" height="28"/>'
                '<rect x="28" y="18" width="6" height="16"/>',
    },
    {
        'id': 'science', 'scene': 'science',
        'name': "Fan", 'title': "Molekulani Qur",
        'color': '#4dd0c0', 'accent': '#9ce9de',
        'max': 26, 'unit': "atom",
        'tagline': "Ilmiy tadqiqotlar, laboratoriya va ixtirolar.",
        'icon': '<circle cx="20" cy="20" r="3"/><circle cx="10" cy="12" r="2.5"/>'
                '<circle cx="30" cy="12" r="2.5"/><circle cx="10" cy="28" r="2.5"/>'
                '<circle cx="30" cy="28" r="2.5"/><path d="M20 20L10 12M20 20l10-8M20 20l-10 8M20 20l10 8"/>',
    },
    {
        'id': 'water', 'scene': 'water',
        'name': "Suv texnologiyalari", 'title': "Daryoni Yarat",
        'color': '#4fa8d8', 'accent': '#a6d8f0',
        'max': 30, 'unit': "tomchi",
        'tagline': "Suvni tejash, tozalash va taqsimlash yechimlari.",
        'icon': '<path d="M20 6c6 8 10 14 10 19a10 10 0 01-20 0c0-5 4-11 10-19z"/>',
    },
]

DIRECTION_MAP = {item['id']: item for item in DIRECTIONS}

#: Model maydonlari uchun choices
DIRECTION_CHOICES = [(item['id'], item['name']) for item in DIRECTIONS]

DEFAULT_DIRECTION = DIRECTIONS[0]['id']


def get_direction(direction_id):
    """Yo'nalishni id bo'yicha qaytaradi; topilmasa birinchisini beradi."""
    return DIRECTION_MAP.get(direction_id, DIRECTIONS[0])


#: Ovoz berilganda chiqadigan ruhlantiruvchi iboralar (tasodifiy tanlanadi).
CHEERS = [
    "G'oya bir qadam o'sdi 🌱",
    "Yana bir ovoz — yana bir imkoniyat",
    "Bu fikr kelajakka yaqinlashdi",
    "Sizning ovozingiz ko'rinib turibdi",
    "Ekotizim jonlanmoqda ✨",
    "Zo'r! G'oya kuch to'plamoqda",
    "Har bir ovoz — kelajakning bir bo'lagi",
    "Bu yo'nalish yorishmoqda 💡",
    "Fikringiz uchun rahmat!",
    "Birgalikda quramiz 🚀",
]

#: Sahna ma'lum bosqichga yetganda chiqadigan alohida xabarlar.
MILESTONES = {
    5: "5 ta ovoz! G'oya ildiz otdi 🌿",
    10: "10 ta ovoz — bu fikr e'tiborni tortmoqda 🔥",
    25: "25 ta ovoz! Yo'nalish gullab-yashnamoqda 🌸",
    50: "50 ta ovoz — bu haqiqiy harakatga aylandi ⭐",
    100: "100 ta ovoz! Kelajak shu yerdan boshlanadi 🏆",
}
