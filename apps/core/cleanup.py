"""Ommaviy o'chirish: yozuvlar va ularga yuklangan fayllar.

Panelning «Hammasini o'chirish» tugmasi va `saytni_tozalash` buyrug'i shundan
foydalanadi. Fayllar baza o'zgarishi muvaffaqiyatli tugagandan keyin o'chadi —
xato bo'lib o'zgarish qaytsa, rasmlar yo'qolib qolmasin.
"""

from django.db import models, transaction


def file_fields(model):
    return [field.name for field in model._meta.get_fields() if isinstance(field, models.FileField)]


def collect_files(queryset):
    names = file_fields(queryset.model)
    if not names:
        return []
    return [getattr(item, name) for item in queryset.iterator()
            for name in names if getattr(item, name)]


def remove_files(files):
    for file in files:
        try:
            file.storage.delete(file.name)
        except OSError:
            pass


def delete_with_files(queryset, *related):
    """Querysetni o'chiradi. `related` — CASCADE bilan birga ketadigan, fayli bor yozuvlar.

    Qaytaradi: (o'chgan asosiy yozuvlar soni, o'chgan fayllar soni).
    """
    with transaction.atomic():
        files = collect_files(queryset)
        for extra in related:
            files.extend(collect_files(extra))
        count = queryset.count()
        queryset.delete()

    remove_files(files)
    return count, len(files)
