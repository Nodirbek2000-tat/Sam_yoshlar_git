"""Har bir yo'nalish uchun namuna tashabbuslar yaratadi.

    python manage.py seed_initiatives
"""

import random

from django.core.management.base import BaseCommand

from apps.initiatives.directions import DIRECTIONS
from apps.initiatives.models import Initiative

AUTHORS = [
    "Aziz Rahimov", "Nilufar Karimova", "Bobur Nazarov", "Madina Yusupova",
    "Jasur Toshmatov", "Dildora Usmonova", "Sherzod Qodirov", "Zulfiya Mirzayeva",
    "Otabek Kamolov", "Gulnora Ahmedova", "Sanjar Ibrohimov", "Kamola Tosheva",
    "Rustam Ergashev", "Sevara Umarova", "Doston Yo'ldoshev", "Feruza Sattorova",
]

REGIONS = [
    'toshkent_shahri', 'toshkent', 'samarqand', 'buxoro', 'fargona',
    'andijon', 'namangan', 'xorazm', 'qashqadaryo', 'jizzax',
]

#: (yo'nalish, [(sarlavha, tavsif, turi)])
IDEAS = {
    'eco': [
        ("Maktablarda plastik yig'ish punktlari", "Har bir maktabda plastik shishalarni topshirish punkti — o'quvchilarga ball beriladi va yil oxirida sovg'a.", 'idea'),
        ("Mahalladagi daraxtlar kesilyapti", "Yangi qurilish tufayli 40 yillik chinorlar kesilmoqda, o'rniga hech narsa ekilmayapti.", 'problem'),
        ("Elektron chiqindi uchun mobil punkt", "Eski telefon va batareykalarni yig'uvchi avtobus haftada bir marta hududlarni aylanadi.", 'proposal'),
        ("Qayta ishlangan qog'ozdan daftar", "Maktab chiqindi qog'ozlarini yig'ib, arzon daftar ishlab chiqarish.", 'startup'),
        ("Ariqlar chiqindi bilan to'lgan", "Yomg'ir suvi oqmayapti, mahalla ariqlari tozalanmagan.", 'problem'),
        ("Har bir tug'ilgan bolaga bitta daraxt", "Tug'ilganlik guvohnomasi bilan birga ko'chat beriladi.", 'idea'),
    ],
    'fintech': [
        ("Talabalar uchun mikro-jamg'arma ilovasi", "Har xariddan qoldiqni avtomatik jamg'armaga o'tkazuvchi ilova.", 'startup'),
        ("Naqd pulsiz bozor", "Dehqon bozorlarida QR orqali to'lov tizimi.", 'idea'),
        ("Kredit shartlari tushunarsiz", "Bank shartnomalarida yashirin to'lovlar ko'p, yoshlar tushunmaydi.", 'problem'),
        ("Moliyaviy savodxonlik boti", "Telegram bot orqali kundalik moliyaviy maslahat.", 'startup'),
    ],
    'ai': [
        ("O'zbek tili uchun ochiq nutq korpusi", "Ovozli yordamchi va subtitr yaratish uchun ochiq audio-matn bazasi.", 'startup'),
        ("Fermerlar uchun kasallik aniqlovchi ilova", "Barg rasmini olib, o'simlik kasalligini aniqlaydigan AI.", 'idea'),
        ("Hujjatlarni avtomatik tekshirish", "Davlat idoralarida hujjat xatolarini AI tekshiradi.", 'proposal'),
        ("Maktab uchun AI repetitor", "O'quvchining zaif mavzusini aniqlab, mashq beradi.", 'startup'),
        ("AI mutaxassislari yetishmayapti", "Bozorda talab bor, lekin tayyorlaydigan kurslar kam.", 'problem'),
    ],
    'edu': [
        ("Qishloq maktablariga onlayn mentorlik", "Toshkentdagi talabalar haftada 2 soat qishloq o'quvchilariga dars beradi.", 'proposal'),
        ("Darsliklar elektron nusxada yo'q", "O'quvchi darslikni yo'qotsa, PDF nusxasini topa olmaydi.", 'problem'),
        ("Kasb tanlash uchun test platformasi", "9-sinf o'quvchilari uchun qiziqish va qobiliyat testi.", 'idea'),
        ("O'qituvchilar uchun video-kutubxona", "Eng yaxshi darslar yozib olinib, hammaga ochiq qo'yiladi.", 'proposal'),
        ("Bepul IT kurslari kerak", "Tumanda dasturlash o'rgatadigan joy yo'q.", 'problem'),
    ],
    'social': [
        ("Nogironligi bor yoshlar uchun IT kurslari", "Bepul dasturlash kurslari va keyin ish bilan ta'minlash.", 'proposal'),
        ("Yolg'iz keksalarga yordam xizmati", "Volontyorlar hafta davomida oziq-ovqat va dori yetkazadi.", 'idea'),
        ("Bolalar uyi bitiruvchilariga qo'llab-quvvatlash", "18 yoshdan keyin uy-joy va ish topishda yordam dasturi.", 'proposal'),
        ("Volontyorlik hisobga olinmaydi", "Yoshlar ko'ngilli ishlaydi, lekin bu tajriba hech qayerda qayd etilmaydi.", 'problem'),
    ],
    'agro': [
        ("Issiqxona uchun avtomatik iqlim nazorati", "Arduino asosidagi arzon nazorat tizimi.", 'startup'),
        ("Hosilni to'g'ridan-to'g'ri sotish platformasi", "Dehqon vositachisiz mijozga sotadi.", 'idea'),
        ("Tomchilatib sug'orish qimmat", "Fermerlar uchun boshlang'ich narx juda baland.", 'problem'),
        ("Tuproq tahlili mobil laboratoriyasi", "Qishloqma-qishloq yurib tuproq tahlilini qiladi.", 'proposal'),
        ("Meva quritish sexi", "Ortiqcha hosilni quritib eksport qilish.", 'startup'),
    ],
    'energy': [
        ("Maktab tomiga quyosh panellari", "Pilot loyiha: 10 ta maktab tomiga panel o'rnatish.", 'idea'),
        ("Ko'chalarda chiroq yonmaydi", "Kechqurun ba'zi ko'chalar qorong'i — xavfsizlik muammosi.", 'problem'),
        ("Quyosh panellarini ijaraga berish", "Katta pul to'lamasdan oyma-oy to'lash modeli.", 'startup'),
        ("Energiya tejash bo'yicha maktab darsi", "O'quvchilarga amaliy energiya tejash o'rgatiladi.", 'proposal'),
    ],
    'industry': [
        ("Mahalliy ehtiyot qismlar katalogi", "Qaysi zavod nima ishlab chiqarishini ko'rsatuvchi ochiq baza.", 'idea'),
        ("Kichik sexlar uchun umumiy ombor", "Bir nechta korxona bitta omborni bo'lishib ishlatadi.", 'proposal'),
        ("Malakali ishchi topilmayapti", "Zavodlarga dastgoh operatorlari yetishmaydi.", 'problem'),
    ],
    'startup': [
        ("Talabalar uchun startap inkubatori", "Universitet qoshida 6 oylik inkubator dasturi.", 'proposal'),
        ("Startaplar uchun huquqiy yordam markazi", "Bepul shartnoma va patent bo'yicha maslahat.", 'idea'),
        ("Investor topish qiyin", "G'oya bor, lekin dastlabki kapital yo'q.", 'problem'),
        ("Startap hamkorlari bozori", "Dasturchi va biznes odam bir-birini topadigan platforma.", 'startup'),
    ],
    'creative': [
        ("Milliy multfilm studiyasi", "O'zbek ertaklari asosida zamonaviy animatsiya.", 'startup'),
        ("Yosh rassomlar uchun onlayn galereya", "Asarlarni sotish va namoyish qilish platformasi.", 'idea'),
        ("Ijodkorlar uchun studiya yo'q", "Musiqa yozish uchun arzon studiya topilmaydi.", 'problem'),
        ("Raqamli dizayn maktabi", "Grafik dizayn va montaj bo'yicha amaliy kurs.", 'proposal'),
        ("Qisqa metrajli kinolar festivali", "Yoshlar uchun yillik festival tashkil etish.", 'idea'),
    ],
    'culture': [
        ("Hunarmandlar uchun onlayn bozor", "Usta hunarmandlar mahsulotini to'g'ridan-to'g'ri sotadi.", 'idea'),
        ("Tarixiy joylar uchun audio-gid", "QR kod orqali o'zbek va ingliz tilida hikoya.", 'startup'),
        ("Milliy hunar o'rgatuvchi ustalar qariyapti", "Yosh shogirdlar yo'q, hunar yo'qolib boryapti.", 'problem'),
        ("Mahalla muzeyi", "Har bir mahallada kichik tarix burchagi.", 'proposal'),
    ],
    'smartcity': [
        ("Avtobus kelish vaqtini ko'rsatuvchi ekran", "Bekatlarga real vaqtda avtobus kelishini ko'rsatuvchi ekran.", 'idea'),
        ("Yo'l chuqurlari haqida xabar berish ilovasi", "Fuqaro rasm yuboradi, tizim manzilni belgilaydi.", 'startup'),
        ("Parkovka joyi topilmaydi", "Markazda mashina qo'yish joyi yetishmaydi.", 'problem'),
        ("Velosiped yo'llari tarmog'i", "Shahar bo'ylab xavfsiz velosiped yo'li.", 'proposal'),
        ("Aqlli svetofor tizimi", "Tirbandlikka qarab yashil chiroq vaqtini o'zgartirish.", 'idea'),
    ],
    'science': [
        ("Maktab laboratoriyalarini yangilash", "Fizika va kimyo xonalariga zamonaviy jihoz.", 'proposal'),
        ("Yosh olimlar uchun grant", "Talabalarning ilmiy loyihalariga kichik moliyalash.", 'idea'),
        ("Ilmiy maqolalar ochiq emas", "Talabalar xalqaro jurnallardan foydalana olmaydi.", 'problem'),
        ("Mobil planetariy", "Maktablarni aylanib yuruvchi astronomiya avtobusi.", 'startup'),
    ],
    'water': [
        ("Tomchilatib sug'orishni arzonlashtirish", "Mahalliy ishlab chiqarish orqali narxni 3 barobar tushirish.", 'startup'),
        ("Ichimlik suvi sifati tekshirilmaydi", "Qishloqlarda quduq suvi tahlil qilinmaydi.", 'problem'),
        ("Yomg'ir suvini yig'ish tizimi", "Tomdan tushgan suvni bog' uchun saqlash.", 'idea'),
        ("Suv hisoblagichlari eskirgan", "Ko'rsatkichlar noto'g'ri, hisob-kitob adolatsiz.", 'problem'),
    ],
}


class Command(BaseCommand):
    help = "Har bir yo'nalishga namuna tashabbuslar qo'shadi (ovozlari turlicha)."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help="Avval mavjud tashabbuslarni o'chiradi")

    def handle(self, *args, **options):
        if options['reset']:
            deleted = Initiative.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"O'chirildi: {deleted}"))

        random.seed(7)   # har safar bir xil natija
        created = 0

        for direction in DIRECTIONS:
            items = IDEAS.get(direction['id'], [])
            for index, (title, description, kind) in enumerate(items):
                if Initiative.objects.filter(title=title).exists():
                    continue

                # Birinchi g'oyalar ko'proq ovoz oladi, oxirgilari kam —
                # reyting jonli ko'rinishi uchun
                ceiling = direction['max']
                if index == 0:
                    votes = random.randint(int(ceiling * 0.55), int(ceiling * 0.9))
                elif index == 1:
                    votes = random.randint(int(ceiling * 0.3), int(ceiling * 0.6))
                elif index == 2:
                    votes = random.randint(int(ceiling * 0.15), int(ceiling * 0.35))
                else:
                    votes = random.randint(0, max(int(ceiling * 0.2), 3))

                Initiative.objects.create(
                    direction=direction['id'],
                    kind=kind,
                    title=title,
                    description=description,
                    summary=description[:150],
                    author_name=random.choice(AUTHORS),
                    region=random.choice(REGIONS),
                    vote_count=votes,
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Yaratildi: {created} ta | Jami: {Initiative.objects.count()} ta"
        ))
