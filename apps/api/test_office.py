"""Samarqand startuplar ofisi: Excel import, ochiq ro'yxat va panel."""

import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XlImage
from PIL import Image

from apps.startups.models import OfficeStartup
from apps.startups.office_import import parse_age, parse_district, parse_phone, project_name

from .auth_views import tokens_for

User = get_user_model()
MEDIA = tempfile.mkdtemp()

HEADER = ['№', 'Hudud', 'F.I.Sh', 'Yoshi', 'Rasmi', 'Ijtimoiy holati', 'Loyiha haqida',
          'StartUp sohasi', 'StartUp bosqichi', 'Loyiha rasmi', 'Telefon raqami',
          "So'ragan mablag'i", 'Batafsil']


def png():
    buffer = BytesIO()
    Image.new('RGB', (40, 40), '#3a8').save(buffer, 'PNG')
    buffer.seek(0)
    return buffer


def workbook(rows, images=True):
    book = Workbook()
    sheet = book.active
    sheet.append(HEADER)
    for index, row in enumerate(rows, start=2):
        sheet.append(row)
        if images:
            sheet.add_image(XlImage(png()), f'E{index}')
            sheet.add_image(XlImage(png()), f'J{index}')
    buffer = BytesIO()
    book.save(buffer)
    return SimpleUploadedFile('reestr.xlsx', buffer.getvalue(),
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


ROWS = [
    [1, 'Samarqand shahar', 'Akbar Gulyamov', '13.06.2000', None, 'Dasturchi',
     'Samly- bu bizneslar uchun CRM platforma.', '💰 FinTech \n— raqamli moliyaviy\n xizmatlar',
     'MVP— mahsulotning eng sodda versiyasi.', None, '+99891 536 81 17', '260 000 000 UZS', 'xarajatlar'],
    [2, 'Urgut tumani', 'Ergashev Ali', 22, None, 'Talaba',
     'Microgreen Uzbekistan — gidroponika usulida mikroko\'katlar.', '🚜 AgriTech \n— aqlli qishloq xo‘jaligi',
     "G'oya", None, '93 860 3606 77 721 4105', '', ''],
]


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


@override_settings(SITE_URL='https://samarqandyoshlari.uz', MEDIA_ROOT=MEDIA)
class OfficeStartupTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="Admin")
        self.user = User.objects.create_user(email='u@test.uz', full_name="Yosh", telegram_id=7)

    def upload(self, file, user=None):
        return self.client.post('/api/v1/panel/office-startups/import/', {'file': file},
                                **auth(user or self.admin))

    # -- import -----------------------------------------------------------------

    def test_import_reads_only_needed_columns_with_images(self):
        response = self.upload(workbook(ROWS))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['created'], 2)

        first = OfficeStartup.objects.get(full_name='Akbar Gulyamov')
        self.assertEqual(first.name, 'Samly')
        self.assertEqual(first.sphere, 'fintech')
        self.assertEqual(first.stage, 'mvp')
        self.assertEqual(first.district, 'samarqand_shahri')
        self.assertEqual(str(first.birth_date), '2000-06-13')
        self.assertEqual(first.phone, '+998915368117')
        self.assertTrue(first.photo)
        self.assertTrue(first.project_image)

        second = OfficeStartup.objects.get(full_name='Ergashev Ali')
        self.assertEqual(second.age, 22)
        self.assertEqual(second.sphere, 'agritech')
        self.assertEqual(second.stage, 'idea')
        self.assertEqual(second.phone, '+998938603606')

    def test_same_project_is_not_imported_twice_but_new_project_is(self):
        self.upload(workbook(ROWS))
        again = self.upload(workbook(ROWS + [[3, 'Urgut tumani', 'Ergashev Ali', 22, None, '',
                                              'Boshqa loyiha — yangi g\'oya', 'EdTech', 'Sotuv',
                                              None, '', '', '']]))
        self.assertEqual(again.json()['created'], 1)
        self.assertEqual(again.json()['duplicates'], 2)
        self.assertEqual(OfficeStartup.objects.filter(full_name='Ergashev Ali').count(), 2)

    def test_wrong_file_is_rejected(self):
        bad = SimpleUploadedFile('reestr.xlsx', b'not excel')
        self.assertEqual(self.upload(bad).status_code, 400)
        csv = SimpleUploadedFile('reestr.csv', b'a,b')
        self.assertEqual(self.upload(csv).status_code, 400)

    def test_import_is_panel_only(self):
        self.assertEqual(self.upload(workbook(ROWS), user=self.user).status_code, 404)
        self.assertFalse(OfficeStartup.objects.exists())

    # -- sayt -------------------------------------------------------------------

    def test_public_list_with_filters_and_contact(self):
        self.upload(workbook(ROWS))
        hidden = OfficeStartup.objects.get(full_name='Ergashev Ali')
        self.client.post(f'/api/v1/panel/office-startups/{hidden.pk}/holat/', {'visible': False},
                         content_type='application/json', **auth(self.admin))

        data = self.client.get('/api/v1/startuplar-ofisi/').json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['total'], 1)
        row = data['results'][0]
        self.assertEqual(row['contact_url'], 'https://t.me/sam_ecobench')
        self.assertNotIn('phone', row)
        self.assertTrue(row['photo'].startswith('https://samarqandyoshlari.uz/media/'))
        self.assertEqual(data['facets']['spheres'][0]['value'], 'fintech')

        self.assertEqual(self.client.get('/api/v1/startuplar-ofisi/?soha=agritech').json()['count'], 0)
        self.assertEqual(self.client.get(f'/api/v1/startuplar-ofisi/{hidden.pk}/').status_code, 404)

    def test_detail_shows_founder_and_related(self):
        self.upload(workbook(ROWS))
        item = OfficeStartup.objects.get(full_name='Akbar Gulyamov')
        data = self.client.get(f'/api/v1/startuplar-ofisi/{item.pk}/').json()
        self.assertEqual(data['full_name'], 'Akbar Gulyamov')
        self.assertEqual(data['district_display'], 'Samarqand shahri')
        self.assertIsInstance(data['age'], int)
        self.assertEqual(data['related'], [])

    # -- panel ------------------------------------------------------------------

    def test_panel_edit_and_telegram_username_wins(self):
        self.upload(workbook(ROWS, images=False))
        item = OfficeStartup.objects.get(full_name='Akbar Gulyamov')
        response = self.client.patch(f'/api/v1/panel/office-startups/{item.pk}/tahrir/',
                                     {'name': 'Samly CRM', 'telegram': 'https://t.me/samly_uz'},
                                     content_type='application/json', **auth(self.admin))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['contact_url'], 'https://t.me/samly_uz')

        bad = self.client.patch(f'/api/v1/panel/office-startups/{item.pk}/tahrir/',
                                {'telegram': 'yomon username!'},
                                content_type='application/json', **auth(self.admin))
        self.assertEqual(bad.status_code, 400)

    def test_panel_delete_removes_files(self):
        self.upload(workbook(ROWS))
        item = OfficeStartup.objects.get(full_name='Akbar Gulyamov')
        path = item.photo.path
        response = self.client.delete(f'/api/v1/panel/office-startups/{item.pk}/', **auth(self.admin))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(OfficeStartup.objects.filter(pk=item.pk).exists())
        import os
        self.assertFalse(os.path.exists(path))

    # -- yordamchilar -------------------------------------------------------------

    def test_parsers(self):
        self.assertEqual(parse_district("Pastdarg'om tumani"), 'pastdargom')
        self.assertEqual(parse_district('Kattaqo‘rg‘on shahri'), 'kattaqorgon_shahri')
        self.assertEqual(parse_age('24.08.2002')[0].year, 2002)
        self.assertEqual(parse_age('abc'), (None, None))
        self.assertEqual(parse_phone('901234567'), '+998901234567')
        self.assertEqual(project_name('Ijara-talaba, talabalarga ijara topish'), 'Ijara-talaba')
        self.assertEqual(project_name('Innavatsion asalari uyasi'), 'Innavatsion asalari uyasi')
