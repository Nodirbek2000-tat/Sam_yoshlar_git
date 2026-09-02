"""Saytdagi mavjud kontent asosida boshlang'ich ma'lumotlarni yaratadi.

    python manage.py seed_demo
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.cabinet.models import Notification
from apps.content.models import Announcement, AnnouncementType, Event, News, NewsCategory
from apps.core.models import Leader, LeaderRole, SiteSetting, Task
from apps.initiatives.models import Organization, OrganizationSphere, Problem, ProblemCategory


class Command(BaseCommand):
    help = "Namuna ma'lumotlarni yaratadi (yangiliklar, tadbirlar, e'lonlar, muammolar)."

    def handle(self, *args, **options):
        self._site_settings()
        self._about()
        self._news()
        self._events()
        self._announcements()
        self._problems()
        self.stdout.write(self.style.SUCCESS("Namuna ma'lumotlar tayyor."))

    def _site_settings(self):
        site = SiteSetting.load()
        site.address = "Toshkent sh., Amir Temur ko'chasi, 4"
        site.phone = "+998 71 123 45 67"
        site.email = "info@samyosh.uz"
        site.work_hours = "Du-Ju: 9:00 — 18:00"
        site.telegram_url = "https://t.me/"
        site.instagram_url = "https://instagram.com/"
        site.facebook_url = "https://facebook.com/"
        site.youtube_url = "https://youtube.com/"
        site.save()
        self.stdout.write("  · Sayt sozlamalari")

    def _about(self):
        tasks = [
            "Yosh tadbirkorlarni aniqlash va ro'yxatga olish",
            "Biznes ta'lim va malaka oshirish dasturlarini tashkil etish",
            "Moliyaviy resurslardan foydalanish imkoniyatlarini yaratish",
            "Hamkorlik aloqalarini o'rnatish va kengaytirish",
            "Tadbirkorlik muhitini yaxshilash bo'yicha takliflar berish",
            "Xalqaro tajriba almashishni tashkil etish",
        ]
        for order, text in enumerate(tasks, start=1):
            Task.objects.get_or_create(text=text, defaults={'order': order})

        leaders = [
            ("Sardor Aliyev", "Kengash Raisi", LeaderRole.CHAIRMAN, '',
             "10 yillik biznes tajribasi. IT sohasida bir nechta muvaffaqiyatli startaplar "
             "asoschisi."),
            ("Nilufar Karimova", "Kengash Kotibi", LeaderRole.SECRETARY, '',
             "Moliya va boshqaruv sohasida 8 yillik tajriba. Xalqaro loyihalar boshqaruvi "
             "bo'yicha mutaxassis."),
            ("Bobur Nazarov", "IT va raqamlashtirish", LeaderRole.MEMBER, 'toshkent_shahri', ''),
            ("Madina Rahimova", "Qishloq xo'jaligi", LeaderRole.MEMBER, 'samarqand', ''),
            ("Jasur Toshmatov", "Ishlab chiqarish", LeaderRole.MEMBER, 'andijon', ''),
            ("Dildora Usmonova", "Xizmat ko'rsatish", LeaderRole.MEMBER, 'buxoro', ''),
            ("Sherzod Qodirov", "Savdo va eksport", LeaderRole.MEMBER, 'fargona', ''),
            ("Zulfiya Mirzayeva", "Ta'lim va innovatsiya", LeaderRole.MEMBER, 'namangan', ''),
            ("Otabek Kamolov", "Turizm", LeaderRole.MEMBER, 'xorazm', ''),
            ("Gulnora Ahmedova", "Sog'liqni saqlash", LeaderRole.MEMBER, 'navoiy', ''),
        ]
        for order, (name, position, role, region, bio) in enumerate(leaders, start=1):
            Leader.objects.get_or_create(full_name=name, defaults={
                'position': position, 'role': role, 'region': region, 'bio': bio, 'order': order,
            })
        self.stdout.write(f"  · Vazifalar va rahbariyat: {len(tasks)} + {len(leaders)} ta")

    def _news(self):
        items = [
            (NewsCategory.GRANT,
             "Yosh tadbirkorlar uchun yangi grant dasturi e'lon qilindi",
             "O'zbekiston Respublikasi hukumati yosh tadbirkorlarni qo'llab-quvvatlash maqsadida "
             "50 mlrd so'mlik grant dasturini e'lon qildi.",
             "Sardor Aliyev", 15),
            (NewsCategory.FORUM,
             "Xalqaro biznes forum: 200 dan ortiq ishtirokchi",
             "Toshkent shahrida bo'lib o'tgan xalqaro biznes forumda 200 dan ortiq yosh tadbirkor "
             "ishtirok etdi.",
             "Nilufar Karimova", 20),
            (NewsCategory.TRAINING,
             "Raqamli marketing bo'yicha bepul trening",
             "Kengash tomonidan tashkil etilgan raqamli marketing treningida 150 nafar yosh "
             "tadbirkor ishtirok etdi.",
             "Bobur Nazarov", 25),
            (NewsCategory.CREDIT,
             "Yangi kredit dasturi: imtiyozli shartlar",
             "Yosh tadbirkorlar uchun 3% stavkada kredit dasturi ishga tushirildi.",
             "Sardor Aliyev", 32),
            (NewsCategory.EXPORT,
             "Eksport qiluvchi korxonalarga yangi imtiyozlar",
             "Eksport hajmini oshirgan yosh tadbirkorlar uchun soliq imtiyozlari joriy etildi.",
             "Sherzod Qodirov", 40),
            (NewsCategory.CONTEST,
             "Startap haftalik: eng yaxshi loyihalar tanlandi",
             "Startap haftalik tanlovida eng yaxshi 10 ta loyiha aniqlandi. G'oliblar investitsiya "
             "jalb qilish imkoniyatiga ega bo'ldi.",
             "Bobur Nazarov", 45),
        ]
        created = 0
        for category, title, excerpt, author, days_ago in items:
            if News.objects.filter(title=title).exists():
                continue
            News.objects.create(
                title=title,
                category=category,
                excerpt=excerpt,
                body=f"{excerpt}\n\nBatafsil ma'lumot uchun Kengash bilan bog'laning. "
                     f"Ariza topshirish tartibi va zarur hujjatlar ro'yxati e'lonlar bo'limida "
                     f"keltirilgan.",
                author_name=author,
                published_at=timezone.now() - timedelta(days=days_ago),
            )
            created += 1
        self.stdout.write(f"  · Yangiliklar: {created} ta")

    def _events(self):
        now = timezone.now()
        items = [
            ("Biznes Accelerator 2024",
             "3 oylik intensiv biznes accelerator dasturi. Mentorlik, trening va investitsiya "
             "imkoniyatlari.",
             now + timedelta(days=14), "09:00", "Toshkent, IT Park", 100),
            ("Networking Night",
             "Tadbirkorlar uchun networking tadbiri. Yangi aloqalar, hamkorlik imkoniyatlari.",
             now + timedelta(days=19), "18:00", "Toshkent, Hilton Hotel", 150),
            ("Export Ready Workshop",
             "Eksportga tayyorlash bo'yicha amaliy seminar. Hujjatlar, logistika, bozor tahlili.",
             now + timedelta(days=35), "10:00", "Samarqand, Registon Business Center", 80),
            ("IT Startup Weekend",
             "48 soatlik hackathon. Eng yaxshi IT loyihalar tanlov asosida tanlanadi.",
             now + timedelta(days=50), "09:00", "Toshkent, IT Park", 200),
            ("Moliyaviy savodxonlik seminari",
             "Biznes moliyasi, buxgalteriya, soliq hisoboti bo'yicha amaliy seminar.",
             now - timedelta(days=20), "14:00", "Buxoro, Savdo-sanoat palatasi", 60),
            ("Qishloq xo'jaligi innovatsiyalari",
             "Zamonaviy agrotexnologiyalar va qishloq xo'jaligida biznes imkoniyatlari.",
             now - timedelta(days=36), "11:00", "Farg'ona, Agro Cluster", 90),
        ]
        created = 0
        for title, description, starts_at, time_str, location, capacity in items:
            if Event.objects.filter(title=title).exists():
                continue
            hour, minute = (int(x) for x in time_str.split(':'))
            # Vaqtni mahalliy (Asia/Tashkent) zonada belgilaymiz
            local = timezone.localtime(starts_at).replace(
                hour=hour, minute=minute, second=0, microsecond=0)
            Event.objects.create(
                title=title,
                description=description,
                starts_at=local,
                location=location,
                capacity=capacity,
            )
            created += 1
        self.stdout.write(f"  · Tadbirlar: {created} ta")

    def _announcements(self):
        today = timezone.localdate()
        items = [
            (AnnouncementType.GRANT,
             "Yosh tadbirkorlar uchun grant — 50 mln so'mgacha",
             "Innovatsion loyihalar uchun qaytarilmaydigan grant. Ariza topshirish muddati cheklangan.",
             28, 30),
            (AnnouncementType.CREDIT,
             "Imtiyozli kredit: yillik 3% stavka",
             "Ishlab chiqarish korxonalari uchun imtiyozli kredit. 5 yil muddat, 1 yil imtiyozli davr.",
             45, 120),
            (AnnouncementType.CONTEST,
             "Eng yaxshi yosh tadbirkor — 2024 tanlovi",
             "Yillik tanlov. G'olib 100 mln so'mlik pul mukofoti va xalqaro ta'lim granti bilan "
             "taqdirlanadi.",
             20, 55),
            (AnnouncementType.TRAINING,
             "Raqamli marketing bo'yicha bepul trening",
             "2 haftalik intensiv kurs. SMM, SEO, kontekstli reklama. Sertifikat beriladi.",
             10, 18),
            (AnnouncementType.VACANCY,
             "Eksport menejeri — vakansiya",
             "Kengash qoshidagi eksport markazi uchun tajribali eksport menejeri kerak. "
             "Maosh: 15-25 mln so'm.",
             12, 25),
            (AnnouncementType.STATE_PROGRAM,
             "Biznesni raqamlashtirish dasturi",
             "Davlat dasturi doirasida korxonalarni raqamlashtirish uchun subsidiya. "
             "50% gacha qoplab beriladi.",
             50, 200),
            (AnnouncementType.SEMINAR,
             "Halal sertifikatlash seminari",
             "Oziq-ovqat korxonalari uchun halal sertifikat olish tartibi bo'yicha seminar.",
             15, 14),
        ]
        created = 0
        for type_, title, body, posted_days_ago, deadline_days in items:
            if Announcement.objects.filter(title=title).exists():
                continue
            Announcement.objects.create(
                type=type_,
                title=title,
                body=body,
                posted_at=today - timedelta(days=posted_days_ago),
                deadline=today + timedelta(days=deadline_days),
            )
            created += 1
        self.stdout.write(f"  · E'lonlar: {created} ta")

    def _problems(self):
        items = [
            ("Samarqand viloyati hokimligi", OrganizationSphere.GOVERNMENT, "Aziz Rahimov",
             "+998 90 111 22 33", ProblemCategory.TECHNOLOGY,
             "Fuqarolar murojaat tizimi sekin ishlaydi, har bir murojaat 5-7 kun kechikadi. "
             "Tizim eskirgan va real-time monitoring imkoniyati yo'q.", 2),
            ("AgroTech Solutions MChJ", OrganizationSphere.AGRICULTURE, "Dilshod Yo'ldoshev",
             "+998 90 222 33 44", ProblemCategory.COMMUNICATION,
             "Fermerlar bilan aloqa qilish va ularning ekinlar holatini kuzatib borish qiyin. "
             "Qo'lda yig'ilgan ma'lumotlar ko'pincha noto'g'ri bo'ladi.", 3),
            ("MedService klinikasi", OrganizationSphere.HEALTHCARE, "Nodira Ismoilova",
             "+998 90 333 44 55", ProblemCategory.BOTTLENECKS,
             "Bemorlar navbat kutish vaqti o'rtacha 2 soat. Shifokorlar ish grafigini "
             "optimallashtirish kerak, navbat tizimi yo'q.", 1),
            ("EduCenter ta'lim markazi", OrganizationSphere.EDUCATION, "Kamola Tosheva",
             "+998 90 444 55 66", ProblemCategory.MANAGEMENT,
             "O'qituvchilarning dars sifatini baholash tizimi yo'q. Talabalar fikr-mulohazasi "
             "yig'ilmaydi va tahlil qilinmaydi.", 5),
            ("LogiTrans yuk tashish", OrganizationSphere.LOGISTICS, "Rustam Ergashev",
             "+998 90 555 66 77", ProblemCategory.TECHNOLOGY,
             "Yuk mashinalarining GPS kuzatuvi yo'q. Haydovchilar yo'nalishdan chetga chiqadi, "
             "yonilg'i xarajatlari nazoratdan tashqarida.", 8),
        ]
        created = 0
        for name, sphere, contact, phone, category, description, days_ago in items:
            if Organization.objects.filter(name=name).exists():
                continue
            organization = Organization.objects.create(
                name=name, sphere=sphere, contact_person=contact, phone=phone,
            )
            problem = Problem.objects.create(
                organization=organization, category=category, description=description,
            )
            # created_at default=timezone.now bo'lgani uchun keyin yangilaymiz
            past = timezone.now() - timedelta(days=days_ago)
            Organization.objects.filter(pk=organization.pk).update(created_at=past)
            Problem.objects.filter(pk=problem.pk).update(created_at=past)
            created += 1
        self.stdout.write(f"  · Tashkilot muammolari: {created} ta")
