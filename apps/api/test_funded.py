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
