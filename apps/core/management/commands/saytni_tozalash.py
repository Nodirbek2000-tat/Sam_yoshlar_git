"""Sinov tugadi — saytni real ishga tayyorlash: namuna va sinov kontentini o'chirish.

    python manage.py saytni_tozalash                  # faqat nima o'chishini sanab ko'rsatadi
    python manage.py saytni_tozalash --ha             # rostdan o'chiradi
    python manage.py saytni_tozalash --ha --userlar   # + oddiy foydalanuvchi hisoblari

O'chiriladi: tashabbuslar (ovoz va izohlari bilan), tashkilot muammolari va
ularga yozilgan takliflar, tashkilotlar, yangiliklar, tadbirlar (yozilishlar
bilan), e'lonlar, chet eldagi tengdoshlar, startaplar, bizneslar (rasmlari
bilan), murojaatlar, sayt takliflari, bildirishnomalar. Yuklangan fayllari ham.

Tegilmaydi: admin va tashkilot hisoblari, sayt sozlamalari, yo'nalishlar.
`--userlar` bo'lsa yosh / tadbirkor / startupper hisoblari ham o'chadi.

Baza qaytarib bo'lmaydigan tarzda o'zgaradi — oldin zaxira nusxa oling.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.abroad.models import Peer
from apps.accounts.models import Role
from apps.business.models import BusinessProfile, Document, GalleryImage, Product
from apps.cabinet.models import Appeal, Notification, Suggestion
from apps.content.models import Announcement, Event, EventRegistration, News
from apps.core.cleanup import collect_files, remove_files
from apps.initiatives.models import (Initiative, InitiativeComment, InitiativeVote, Organization,
                                     Problem, Solution, SolutionLike)
from apps.startups.models import Startup

#: Tartib muhim — bog'liq yozuvlar oldin o'chadi
CONTENT = [
    ("Tashabbus izohlari", InitiativeComment),
    ("Tashabbus ovozlari", InitiativeVote),
    ("Tashabbuslar", Initiative),
    ("Taklif layklari", SolutionLike),
    ("Muammolarga takliflar", Solution),
    ("Tashkilot muammolari", Problem),
    ("Tashkilotlar", Organization),
    ("Tadbirga yozilishlar", EventRegistration),
    ("Tadbirlar", Event),
    ("Yangiliklar", News),
    ("E'lonlar", Announcement),
    ("Chet eldagi tengdoshlar", Peer),
    ("Startaplar", Startup),
    ("Biznes rasmlari", GalleryImage),
    ("Biznes mahsulotlari", Product),
    ("Biznes hujjatlari", Document),
    ("Bizneslar", BusinessProfile),
    ("Murojaatlar", Appeal),
    ("Sayt takliflari", Suggestion),
    ("Bildirishnomalar", Notification),
]


class Command(BaseCommand):
    help = "Namuna va sinov kontentini o'chiradi. `--ha` berilmasa faqat sanab ko'rsatadi."

    def add_arguments(self, parser):
        parser.add_argument('--ha', action='store_true', help="Rostdan o'chirish")
        parser.add_argument('--userlar', action='store_true',
                            help="Yosh, tadbirkor va startupper hisoblarini ham o'chirish")

    def handle(self, *args, **options):
        users = (get_user_model().objects.filter(is_superuser=False, is_staff=False)
                 .exclude(role__in=[Role.ADMIN, Role.ORGANIZATION]))

        self.stdout.write("O'chiriladi:")
        for label, model in CONTENT:
            self.stdout.write(f"  {label:<26} {model.objects.count()}")
        if options['userlar']:
            self.stdout.write(f"  {'Foydalanuvchi hisoblari':<26} {users.count()}")

        if not options['ha']:
            self.stdout.write(self.style.WARNING(
                "\nHech narsa o'chirilmadi. Rostdan o'chirish uchun: --ha"))
            return

        # Fayllar baza o'zgarishi muvaffaqiyatli tugagandan keyin o'chiriladi
        files = []
        with transaction.atomic():
            for _label, model in CONTENT:
                files.extend(collect_files(model.objects.all()))
                model.objects.all().delete()

            if options['userlar']:
                files.extend(collect_files(users))
                users.delete()

        remove_files(files)

        self.stdout.write(self.style.SUCCESS(
            f"\nTayyor: kontent o'chirildi, {len(files)} ta fayl tozalandi."))
