"""Yuklangan rasmlarni saqlashdan oldin siqish.

Telefondan tushgan rasm 4–5 MB, 4000 px bo'ladi — sayt kartasida esa u
300–600 px joy egallaydi. Shuning uchun har bir yangi rasm saqlanishdan
oldin kichraytiriladi:

* eng katta tomoni ``MAX_SIDE`` dan oshmaydi;
* shaffof joyi bor rasm (logotip) PNG bo'lib qoladi, qolgani JPEG;
* telefon burib yuborgan rasm (EXIF) to'g'rilanadi;
* natija kichikroq bo'lmasa — asl fayl o'zgarishsiz qoladi.

``pre_save`` signali hamma modeldagi ``ImageField`` ga ishlaydi: panel,
kabinet, admin — qayerdan yuklansa ham. Mavjud rasmlarni esa
``rasmlarni_siqish`` buyrug'i bir marta siqib chiqadi.
"""

import io
import logging
from pathlib import PurePath

from django.core.files.base import ContentFile
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

#: Rasmning eng katta tomoni (px) — keng ekranda ham yetarli
MAX_SIDE = 1920
JPEG_QUALITY = 82
#: Shundan kichik va o'lchami me'yorida bo'lgan rasmga tegmaymiz
SMALL_ENOUGH = 200 * 1024


def image_fields(model):
    return [field for field in model._meta.concrete_fields if isinstance(field, models.ImageField)]


def _has_transparency(image):
    if image.mode in ('RGBA', 'LA'):
        return image.getchannel('A').getextrema()[0] < 255
    if image.mode == 'P' and 'transparency' in image.info:
        return image.convert('RGBA').getchannel('A').getextrema()[0] < 255
    return False


def compress(source, name):
    """Siqilgan rasm: ``(bayt, yangi_nom)`` yoki ``None`` — siqish shart emas bo'lsa.

    ``source`` — o'qiladigan fayl obyekti, ``name`` — asl nomi.
    """
    try:
        source.seek(0)
        raw = source.read()
    except (OSError, ValueError):
        return None

    try:
        image = Image.open(io.BytesIO(raw))
        # Animatsiyali GIF/WebP — kadrlar yo'qolmasin
        if getattr(image, 'is_animated', False):
            return None
        # JPEG'ni to'liq o'lchamda ochmasdan, keraklisigacha kichraytirib o'qiydi (tez)
        image.draft('RGB', (MAX_SIDE, MAX_SIDE))
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        return None

    too_big = max(image.size) > MAX_SIDE
    if not too_big and len(raw) <= SMALL_ENOUGH:
        return None

    if too_big:
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    stem = PurePath(name).stem or 'rasm'

    if _has_transparency(image):
        image = image.convert('RGBA')
        image.save(buffer, format='PNG', optimize=True)
        new_name = f"{stem}.png"
    else:
        image = image.convert('RGB')
        image.save(buffer, format='JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
        new_name = f"{stem}.jpg"

    data = buffer.getvalue()
    # Kichraytirilmagan va siqish foyda bermagan bo'lsa — asl fayl qoladi
    if not too_big and len(data) >= len(raw):
        return None
    return data, new_name


@receiver(pre_save, dispatch_uid='core_compress_images')
def compress_uploaded_images(sender, instance, raw=False, **kwargs):
    """Yangi yuklangan (hali diskka yozilmagan) rasmlarni siqadi."""
    if raw:  # loaddata
        return

    for field in image_fields(sender):
        file = getattr(instance, field.attname)
        if not file or getattr(file, '_committed', True):
            continue

        try:
            result = compress(file.file, file.name)
        except Exception:                       # noqa: BLE001 — rasm tufayli saqlash to'xtamasin
            logger.exception("Rasmni siqib bo'lmadi: %s", file.name)
            continue

        if result is not None:
            data, new_name = result
            setattr(instance, field.attname, ContentFile(data, name=new_name))
