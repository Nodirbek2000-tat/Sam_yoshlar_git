"""Mablag' olgan startaplar: panelda qo'shish, saytda ro'yxat va jami mablag'."""

import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.startups.models import FundedStartup

from .auth_views import tokens_for
from .tests import _png

User = get_user_model()
MEDIA = tempfile.mkdtemp(prefix='mablag-test-')


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


@override_settings(MEDIA_ROOT=MEDIA, SITE_URL='https://samarqandyoshlari.uz')
class FundedStartupTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")
        self.user = User.objects.create_user(email='u@test.uz', full_name="U")

    def add(self, user=None, **extra):
        data = {'name': "Tilchi AI", 'founder': "Ali Valiyev", 'amount': '500000000',
                'currency': 'UZS', 'funder': "IT Park", 'year': '2026', 'order': '1',
                'about': "Ovozli yordamchi.", 'is_published': 'true',
                'image_file': _png('rasm.png'), **extra}
        return self.client.post('/api/v1/panel/funded/', data, **auth(user or self.admin))

    def test_panel_adds_and_site_lists_with_totals(self):
        self.assertEqual(self.add().status_code, 201)
        self.add(name="AgroBot", amount='20000', currency='USD', order='0', image_file=_png())
        self.add(name="Yashirin", is_published='false', image_file=_png())

        data = self.client.get('/api/v1/mablag-olganlar/').json()
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['totals'], {'UZS': 500000000, 'USD': 20000})
        # Tartib bo'yicha: kichigi oldinda
        self.assertEqual([row['name'] for row in data['results']], ["AgroBot", "Tilchi AI"])
        self.assertTrue(data['results'][1]['image'].startswith('https://samarqandyoshlari.uz/media/mablag/'))
        self.assertEqual(data['results'][1]['currency_display'], "so'm")

    def test_panel_only(self):
        self.assertEqual(self.add(user=self.user).status_code, 404)
        self.assertFalse(FundedStartup.objects.exists())

    def test_edit_hide_and_delete_removes_image(self):
        item_id = self.add().json()['id']
        response = self.client.patch(f'/api/v1/panel/funded/{item_id}/tahrir/', {'amount': 750000000},
                                     content_type='application/json', **auth(self.admin))
        self.assertEqual(response.json()['amount'], 750000000)

        self.client.post(f'/api/v1/panel/funded/{item_id}/holat/', {'visible': False},
                         content_type='application/json', **auth(self.admin))
        self.assertEqual(self.client.get('/api/v1/mablag-olganlar/').json()['count'], 0)

        path = FundedStartup.objects.get(pk=item_id).image.path
        self.client.delete(f'/api/v1/panel/funded/{item_id}/', **auth(self.admin))
        self.assertFalse(os.path.exists(path))

    def test_bad_year_rejected(self):
        self.assertEqual(self.add(year='1990').status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA, SITE_URL='https://samarqandyoshlari.uz')
class FundedMediaAndBotTests(TestCase):
    def setUp(self):
        from apps.accounts.models import BotSetting

        self.admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")
        setting = BotSetting.load()
        setting.auto_post = True
        setting.save()

    def video(self, name='demo.mp4', size=1024):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, b'\x00' * size, content_type='video/mp4')

    def test_several_photos_video_and_bot_message(self):
        from apps.accounts.models import BotPost

        response = self.client.post('/api/v1/panel/funded/', {
            'name': "Tilchi AI", 'amount': '500000000', 'currency': 'UZS', 'funder': "IT Park",
            'founder': "Ali Valiyev", 'about': "Ovozli yordamchi.", 'is_published': 'true',
            'image_file': _png('muqova.png'), 'new_photos': [_png('1.png'), _png('2.png')],
            'video_file': self.video(),
        }, **auth(self.admin))
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(len(body['photos']), 2)
        self.assertIn('/media/mablag/video/', body['video'])

        public = self.client.get('/api/v1/mablag-olganlar/').json()['results'][0]
        self.assertEqual(len(public['photos']), 2)

        post = BotPost.objects.get(kind=BotPost.Kind.FUNDED)
        self.assertEqual(post.title, "Tilchi AI 500 mln so'm mablag' oldi! 🎉")
        self.assertIn("IT Park tomonidan 500 mln so'm ajratildi.", post.excerpt)
        self.assertIn("\n", post.excerpt)
        self.assertTrue(post.link.endswith(f"/?mablag={body['id']}"))
        self.assertIn('/media/mablag/', post.image_url)

        # Tahrirlansa — ikkinchi marta yuborilmaydi; rasm o'chirish va video almashtirish
        first = body['photos'][0]['id']
        old_video = FundedStartup.objects.get(pk=body['id']).video.path
        from django.test.client import encode_multipart
        edited = self.client.patch(
            f"/api/v1/panel/funded/{body['id']}/tahrir/",
            data=encode_multipart('BoUnD', {'remove_photos': [first], 'video_file': self.video('yangi.mp4')}),
            content_type='multipart/form-data; boundary=BoUnD', **auth(self.admin))
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(len(edited.json()['photos']), 1)
        self.assertFalse(os.path.exists(old_video))
        self.assertEqual(BotPost.objects.filter(kind=BotPost.Kind.FUNDED).count(), 1)

        # O'chirilsa — galereya rasmlari va video ham diskdan ketadi
        item = FundedStartup.objects.get(pk=body['id'])
        files = [item.video.path, item.image.path] + [p.image.path for p in item.photos.all()]
        self.client.delete(f"/api/v1/panel/funded/{body['id']}/", **auth(self.admin))
        for path in files:
            self.assertFalse(os.path.exists(path))

    def test_video_limits(self):
        too_big = self.client.post('/api/v1/panel/funded/', {
            'name': "Katta", 'video_file': self.video(size=50 * 1024 * 1024 + 1)}, **auth(self.admin))
        self.assertEqual(too_big.status_code, 400)
        wrong = self.client.post('/api/v1/panel/funded/', {
            'name': "Avi", 'video_file': self.video('demo.avi')}, **auth(self.admin))
        self.assertEqual(wrong.status_code, 400)

    def test_hidden_startup_is_not_announced(self):
        from apps.accounts.models import BotPost

        self.client.post('/api/v1/panel/funded/', {'name': "Yashirin", 'is_published': 'false'},
                         **auth(self.admin))
        self.assertFalse(BotPost.objects.exists())
