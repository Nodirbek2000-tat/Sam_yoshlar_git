"""«Mirzo Ulug'bek vorislari»: Excel import, ochiq ro'yxat va panel."""

import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XlImage
from PIL import Image

from apps.startups.models import Laureate

from .auth_views import tokens_for

User = get_user_model()
MEDIA = tempfile.mkdtemp(prefix='vorislar-test-')


def png():
    buffer = BytesIO()
    Image.new('RGB', (40, 50), '#36c').save(buffer, 'PNG')
    buffer.seek(0)
    return buffer


def workbook(rows, header, title=None):
    book = Workbook()
    sheet = book.active
    sheet.append([title or "G'oliblar"])
    sheet.append(header)
    for index, row in enumerate(rows, start=3):
        sheet.append(row)
        sheet.add_image(XlImage(png()), f'{chr(64 + len(header))}{index}')
    buffer = BytesIO()
    book.save(buffer)
    return SimpleUploadedFile('vorislar.xlsx', buffer.getvalue())


HEADER = ['№', 'Yil', 'F.I.Sh', 'Tuman', 'Loyiha nomi', 'Loyiha haqida', "Tug'ilgan sana",
          'Yoshi', "Ta'lim muassasasi", 'Kurs / sinf', "Respublika g'olibi", 'Rasmi']
ROWS = [
    [1, 2026, "Ravshanov Asilbek", 'Paxtachi', 'Smart gateX', "Aqlli darvoza.", '07.05.2004', 22,
     'NDKTU', 4, 'Ha', None],
    [2, 2025, "Furqatova Madina", 'Jomboy tuman', 'LingvoKino', "Kino orqali til.", '01.12.2005', 19,
     'SamDCHTI', 1, '', None],
]


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


@override_settings(MEDIA_ROOT=MEDIA, SITE_URL='https://samarqandyoshlari.uz')
class LaureateTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")
        self.user = User.objects.create_user(email='u@test.uz', full_name="U")

    def upload(self, file, user=None):
        return self.client.post('/api/v1/panel/laureates/import/', {'file': file},
                                **auth(user or self.admin))

    def test_import_reads_columns_photos_and_skips_duplicates(self):
        response = self.upload(workbook(ROWS, HEADER))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['created'], 2)

        item = Laureate.objects.get(full_name="Ravshanov Asilbek")
        self.assertEqual((item.year, item.district, item.course), (2026, "Paxtachi tumani", "4-kurs"))
        self.assertTrue(item.is_national_winner)
        self.assertTrue(item.photo)
        self.assertEqual(Laureate.objects.get(full_name="Furqatova Madina").district, "Jomboy tumani")

        again = self.upload(workbook(ROWS, HEADER)).json()
        self.assertEqual((again['created'], again['duplicates']), (0, 2))

    def test_year_from_title_when_no_year_column(self):
        header = ['№', 'F.I.SH', 'Tuman', 'Loyiha nomi', 'Kun, oy, yil', 'Yoshi', 'Rasmi']
        rows = [[1, "Bebitova Shoxsanam", "Qo'shrabot tumani", 'Biofiksplastr', '23.04.2000', 25, None]]
        self.upload(workbook(rows, header, title="G'oliblar to'g'risida MA'LUMOT - 2025"))
        item = Laureate.objects.get()
        self.assertEqual((item.year, item.age, str(item.birth_date)), (2025, 25, '2000-04-23'))

    def test_import_is_panel_only(self):
        self.assertEqual(self.upload(workbook(ROWS, HEADER), user=self.user).status_code, 404)

    def test_public_list_years_and_detail(self):
        self.upload(workbook(ROWS, HEADER))
        hidden = Laureate.objects.get(full_name="Furqatova Madina")
        self.client.post(f'/api/v1/panel/laureates/{hidden.pk}/holat/', {'visible': False},
                         content_type='application/json', **auth(self.admin))

        data = self.client.get('/api/v1/vorislar/').json()
        self.assertEqual((data['count'], data['total'], data['national']), (1, 1, 1))
        self.assertEqual(data['years'], [{'value': 2026, 'count': 1}])
        row = data['results'][0]
        self.assertNotIn('phone', row)
        self.assertTrue(row['photo'].startswith('https://samarqandyoshlari.uz/media/vorislar/'))

        self.assertEqual(self.client.get('/api/v1/vorislar/?yil=2025').json()['count'], 0)
        self.assertEqual(self.client.get(f'/api/v1/vorislar/{hidden.pk}/').status_code, 404)
        item = Laureate.objects.get(full_name="Ravshanov Asilbek")
        self.assertEqual(self.client.get(f'/api/v1/vorislar/{item.pk}/').json()['related'], [])

    def test_panel_edit_and_delete_removes_photo(self):
        self.upload(workbook(ROWS, HEADER))
        item = Laureate.objects.get(full_name="Ravshanov Asilbek")
        response = self.client.patch(f'/api/v1/panel/laureates/{item.pk}/tahrir/',
                                     {'about': "Yangi tavsif", 'year': 2025},
                                     content_type='application/json', **auth(self.admin))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['about'], "Yangi tavsif")

        import os
        path = item.photo.path
        self.client.delete(f'/api/v1/panel/laureates/{item.pk}/', **auth(self.admin))
        self.assertFalse(os.path.exists(path))
