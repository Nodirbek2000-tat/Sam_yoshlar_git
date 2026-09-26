"""Yuklangan rasmlarni siqish: signal, qoidalar va mavjud rasmlar buyrug'i."""

import io
import shutil
import tempfile

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from apps.content.models import News

from .images import MAX_SIDE, compress

MEDIA = tempfile.mkdtemp(prefix='rasm-test-')


def photo(size=(4000, 3000), fmt='JPEG', mode='RGB', noise=True):
    """Haqiqiy kattalikdagi «telefon rasmi» — shovqin bilan, siqilishi qiyin bo'lsin."""
    image = Image.new(mode, size, (40, 120, 200) if mode == 'RGB' else (40, 120, 200, 255))
    if noise:
        image = Image.effect_noise(size, 60).convert(mode) if mode == 'RGB' else image
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, quality=95) if fmt == 'JPEG' else image.save(buffer, format=fmt)
    return buffer.getvalue()


class CompressRulesTests(TestCase):
    def test_big_photo_is_resized_to_max_side(self):
        data, name = compress(io.BytesIO(photo()), 'IMG_2031.JPG')
        result = Image.open(io.BytesIO(data))
        self.assertEqual(max(result.size), MAX_SIDE)
        self.assertEqual(result.size, (1920, 1440))      # nisbat saqlanadi
        self.assertEqual(result.format, 'JPEG')
        self.assertEqual(name, 'IMG_2031.jpg')

    def test_small_image_is_left_alone(self):
        self.assertIsNone(compress(io.BytesIO(photo((600, 400), noise=False)), 'kichik.jpg'))

    def test_transparent_logo_stays_png(self):
        image = Image.new('RGBA', (2400, 2400), (0, 0, 0, 0))
        image.paste((200, 30, 30, 255), (600, 600, 1800, 1800))
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')

        data, name = compress(io.BytesIO(buffer.getvalue()), 'logo.png')
        result = Image.open(io.BytesIO(data))
        self.assertEqual(result.format, 'PNG')
        self.assertEqual(result.mode, 'RGBA')
        self.assertEqual(name, 'logo.png')
        self.assertEqual(max(result.size), MAX_SIDE)

    def test_png_photo_without_transparency_becomes_jpeg(self):
        data, name = compress(io.BytesIO(photo((3000, 2000), fmt='PNG')), 'Group_2851.png')
        self.assertEqual(Image.open(io.BytesIO(data)).format, 'JPEG')
        self.assertEqual(name, 'Group_2851.jpg')

    def test_phone_rotation_is_applied(self):
        image = Image.effect_noise((3000, 2000), 60).convert('RGB')
        exif = image.getexif()
        exif[0x0112] = 6                                # telefon: 90° burilgan
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', exif=exif, quality=95)

        data, _ = compress(io.BytesIO(buffer.getvalue()), 'burilgan.jpg')
        self.assertEqual(Image.open(io.BytesIO(data)).size, (1280, 1920))   # tik holatga keldi

    def test_not_an_image_is_ignored(self):
        self.assertIsNone(compress(io.BytesIO(b'bu rasm emas'), 'x.jpg'))


@override_settings(MEDIA_ROOT=MEDIA)
class UploadSignalTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def _news(self, **extra):
        return News.objects.create(title="Rasm sinovi", excerpt="Qisqa", body="Matn",
                                   category='boshqa', is_published=True, **extra)

    def test_uploaded_photo_is_compressed_before_saving(self):
        upload = SimpleUploadedFile('telefon.jpg', photo(), content_type='image/jpeg')
        original = len(upload.read())
        upload.seek(0)

        news = self._news(image=upload)
        news.refresh_from_db()

        self.assertTrue(news.image.name.endswith('.jpg'))
        self.assertLess(news.image.size, original)
        with news.image.open('rb') as handle:
            self.assertEqual(max(Image.open(handle).size), MAX_SIDE)

    def test_editing_other_fields_does_not_touch_saved_image(self):
        news = self._news(image=SimpleUploadedFile('a.jpg', photo(), content_type='image/jpeg'))
        name = news.image.name

        news.title = "Yangi sarlavha"
        news.save()
        news.refresh_from_db()
        self.assertEqual(news.image.name, name)

    def test_existing_images_command(self):
        news = self._news()
        # Signalni chetlab, «eski» og'ir rasmni to'g'ridan-to'g'ri yozamiz
        name = news.image.storage.save('news/eski.jpg', ContentFile(photo()))
        News.objects.filter(pk=news.pk).update(image=name)
        size_before = news.image.storage.size(name)

        call_command('rasmlarni_siqish', stdout=io.StringIO())      # faqat hisoblaydi
        news.refresh_from_db()
        self.assertEqual(news.image.name, name)

        call_command('rasmlarni_siqish', '--ha', stdout=io.StringIO())
        news.refresh_from_db()
        self.assertNotEqual(news.image.name, name)
        self.assertLess(news.image.size, size_before)
        self.assertFalse(news.image.storage.exists(name))           # eskisi o'chdi
