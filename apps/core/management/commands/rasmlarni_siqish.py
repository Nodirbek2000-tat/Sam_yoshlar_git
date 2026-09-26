"""Saytdagi mavjud rasmlarni bir marta siqib chiqish.

    python manage.py rasmlarni_siqish          # faqat qancha joy tejalishini hisoblaydi
    python manage.py rasmlarni_siqish --ha     # rostdan siqadi

Yangi yuklanadigan rasmlar o'zi siqiladi (``apps/core/images.py``). Bu buyruq
undan oldin yuklangan og'ir rasmlar uchun: eng katta tomoni 1920 px ga
tushiriladi, JPEG 82% sifatda saqlanadi. Yangi fayl yoziladi, eskisi
o'chiriladi, bazadagi havola yangilanadi.

Baza ``update()`` bilan yangilanadi — saqlash signallari ishlamaydi, ya'ni
eski yangiliklar botga qayta yuborilib ketmaydi.
"""

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.core.images import compress, image_fields


def human(size):
    return f"{size / 1024 / 1024:.1f} MB" if size >= 1024 * 1024 else f"{size / 1024:.0f} KB"


class Command(BaseCommand):
    help = "Mavjud rasmlarni siqadi (standart holatda faqat hisoblaydi)"

    def add_arguments(self, parser):
        parser.add_argument('--ha', action='store_true', help="Rostdan siqish")

    def handle(self, *args, **options):
        apply = options['ha']
        before_total = after_total = changed = failed = 0

        for model in apps.get_models():
            fields = image_fields(model)
            if not fields:
                continue

            for field in fields:
                queryset = (model.objects.exclude(**{field.attname: ''})
                            .exclude(**{f'{field.attname}__isnull': True})
                            .only('pk', field.attname))

                for item in queryset.iterator():
                    file = getattr(item, field.attname)
                    storage = file.storage
                    old_name = file.name

                    if not storage.exists(old_name):
                        continue

                    try:
                        with storage.open(old_name, 'rb') as handle:
                            size = storage.size(old_name)
                            result = compress(handle, old_name)
                    except OSError as error:
                        failed += 1
                        self.stderr.write(f"  o'qib bo'lmadi: {old_name} ({error})")
                        continue

                    if result is None:
                        continue

                    data, new_name = result
                    before_total += size
                    after_total += len(data)
                    changed += 1
                    self.stdout.write(f"  {model._meta.label}.{field.name}: {old_name} "
                                      f"{human(size)} -> {human(len(data))}")

                    if not apply:
                        continue

                    # Yangi faylni o'sha papkaga yozamiz (upload_to qayta hisoblanadi)
                    target = field.generate_filename(item, new_name)
                    saved = storage.save(target, ContentFile(data))
                    model.objects.filter(pk=item.pk).update(**{field.attname: saved})
                    if saved != old_name:
                        storage.delete(old_name)

        verb = "siqildi" if apply else "siqiladi"
        self.stdout.write(self.style.SUCCESS(
            f"\n{changed} ta rasm {verb}: {human(before_total)} -> {human(after_total)} "
            f"(tejaldi: {human(before_total - after_total)})"))
        if failed:
            self.stdout.write(self.style.WARNING(f"{failed} ta faylni o'qib bo'lmadi"))
        if not apply and changed:
            self.stdout.write("Rostdan siqish uchun: python manage.py rasmlarni_siqish --ha")
