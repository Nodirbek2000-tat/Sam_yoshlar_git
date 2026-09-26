"""E'lon: rasm (ikonka o'rniga), «Murojaat qilish» havolasi va panel havolalari."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.bot_feed import shorten
from apps.content.models import Announcement

from .auth_views import tokens_for
from .tests import _png

User = get_user_model()
MEDIA = tempfile.mkdtemp(prefix='elon-test-')


@override_settings(MEDIA_ROOT=MEDIA)
class AnnouncementMediaTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(admin)['access']}"}

    def create(self, **extra):
        data = {'title': "Yoshlar biznesi mikroqarzi", 'type': 'kredit',
                'body': "Matn", 'is_active': 'true', **extra}
        return self.client.post('/api/v1/panel/announcements/', data, **self.auth)

    def test_image_and_apply_link_reach_the_site(self):
        response = self.create(image=_png('muqova.png'),
                               apply_url='https://aloqabank.uz/uz/private/crediting/')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIn('/media/announcements/images/', response.json()['image_url'])

        slug = response.json()['slug']
        public = self.client.get(f'/api/v1/announcements/{slug}/').json()
        self.assertIn('/media/announcements/images/', public['image'])
        self.assertEqual(public['apply_url'], 'https://aloqabank.uz/uz/private/crediting/')

        listed = self.client.get('/api/v1/announcements/').json()['results'][0]
        self.assertTrue(listed['image'])

    def test_bad_apply_link_rejected(self):
        response = self.create(apply_url='bu-havola-emas')
        self.assertEqual(response.status_code, 400)
        self.assertIn('apply_url', response.json())

    def test_image_can_be_replaced_and_removed(self):
        item_id = self.create(image=_png('birinchi.png')).json()['id']
        url = f'/api/v1/panel/announcements/{item_id}/tahrir/'

        # Boshqa maydonni tahrirlash rasmga tegmaydi
        self.client.patch(url, {'title': "Yangi nom"}, **self.auth,
                          content_type='application/json')
        self.assertTrue(Announcement.objects.get(pk=item_id).image)

        from django.test.client import encode_multipart, BOUNDARY, MULTIPART_CONTENT
        body = encode_multipart(BOUNDARY, {'remove_image': 'on'})
        response = self.client.patch(url, body, content_type=MULTIPART_CONTENT, **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()['image_url'])
        self.assertFalse(Announcement.objects.get(pk=item_id).image)

    def test_deleting_one_item_removes_its_image(self):
        item_id = self.create(image=_png('ochadi.png')).json()['id']
        image = Announcement.objects.get(pk=item_id).image
        self.assertTrue(image.storage.exists(image.name))

        response = self.client.delete(f'/api/v1/panel/announcements/{item_id}/', **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(image.storage.exists(image.name))

    def test_import_accepts_apply_url(self):
        payload = {'announcements': [
            {'title': "Birinchi", 'type': 'grant', 'body': "X",
             'apply_url': 'https://tashkilot.uz/ariza'},
            {'title': "Ikkinchi", 'type': 'grant', 'body': "Y", 'apply_url': 'yomon'},
        ]}
        data = self.client.post('/api/v1/panel/import/announcements/', payload,
                                content_type='application/json', **self.auth).json()
        self.assertEqual(data['created'], 2)
        self.assertEqual(Announcement.objects.get(title="Birinchi").apply_url,
                         'https://tashkilot.uz/ariza')
        self.assertEqual(Announcement.objects.get(title="Ikkinchi").apply_url, '')
        self.assertTrue(data['problems'])

    def test_panel_overview_has_no_dead_links(self):
        data = self.client.get('/api/v1/panel/overview/', **self.auth).json()
        hrefs = {row['key']: row['href'] for row in data['pending']}
        self.assertNotIn('appeals', hrefs)
        self.assertNotIn('suggestions', hrefs)
        self.assertEqual(hrefs['solutions'], '/nazorat/muammolar')


class BotExcerptTests(TestCase):
    def test_markup_is_removed_for_telegram(self):
        text = shorten("# Grant\n**Qaytarilmaydigan** grant.\n- Shart\n[Ariza](https://x.uz)")
        self.assertEqual(text, "Grant Qaytarilmaydigan grant. Shart Ariza")
