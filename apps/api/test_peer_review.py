"""Chet eldagi tengdosh: anketa admin tasdig'idan keyin saytga va botga chiqadi."""

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from apps.abroad.models import Peer
from apps.accounts.models import BotMessage, BotPost, BotSetting
from apps.cabinet.models import Notification

from .auth_views import tokens_for

User = get_user_model()

def photo():
    """Haqiqiy kichik rasm — anketada rasm majburiy."""
    buffer = BytesIO()
    Image.new('RGB', (20, 20), '#3a8').save(buffer, 'PNG')
    return SimpleUploadedFile('p.png', buffer.getvalue(), content_type='image/png')


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


@override_settings(SITE_URL='https://samarqandyoshlari.uz')
class PeerReviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x',
                                                   full_name="Admin", telegram_id=500)
        self.student = User.objects.create_user(email='s@test.uz', full_name="Sardor Nazarov",
                                                role='yosh', telegram_id=700)
        setting = BotSetting.load()
        setting.auto_post = True
        setting.save()

    def apply(self, **changes):
        form = {'country': 'usa', 'city': 'Boston', 'institution': "MIT", 'course': 2,
                'field': "Informatika", 'phone': '+998901112233',
                'photo': photo(), **changes}
        return self.client.post('/api/v1/me/peer/', form, **auth(self.student))

    def moderate(self, peer, status):
        return self.client.post(f'/api/v1/panel/peers/{peer.pk}/holat/', {'status': status},
                                content_type='application/json', **auth(self.admin))

    def public_ids(self):
        return [row['id'] for row in self.client.get('/api/v1/peers/').json()['results']]

    def test_new_application_waits_for_admin(self):
        response = self.apply()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['status'], 'pending')

        peer = Peer.objects.get()
        self.assertNotIn(peer.pk, self.public_ids())
        self.assertFalse(BotPost.objects.exists())

        # Panel adminiga Telegram'da xabar
        message = BotMessage.objects.get()
        self.assertEqual(message.telegram_id, 500)
        self.assertIn("Sardor Nazarov", message.text)
        self.assertTrue(message.buttons[0]['url'].endswith('/nazorat/tengdoshlar'))

        # Panelda «tasdiq kutayotganlar» ro'yxatida
        pending = {row['key']: row['value'] for row in
                   self.client.get('/api/v1/panel/overview/', **auth(self.admin)).json()['pending']}
        self.assertEqual(pending['peers'], 1)

    def test_approval_publishes_to_site_and_bot(self):
        self.apply()
        peer = Peer.objects.get()
        BotMessage.objects.all().delete()

        self.assertEqual(self.moderate(peer, 'approved').status_code, 200)

        self.assertIn(peer.pk, self.public_ids())
        post = BotPost.objects.get()
        self.assertTrue(post.link.endswith(f'/tengdoshlar/{peer.pk}'))

        note = Notification.objects.get(user=self.student)
        self.assertEqual(note.title, "Anketangiz tasdiqlandi")
        message = BotMessage.objects.get()
        self.assertEqual(message.telegram_id, 700)
        self.assertIn("tasdiqlandi", message.text)

    def test_rejected_application_goes_back_to_review_after_edit(self):
        self.apply()
        peer = Peer.objects.get()
        self.moderate(peer, 'rejected')
        self.assertEqual(Notification.objects.get(user=self.student).title, "Anketangiz qaytarildi")
        self.assertNotIn(peer.pk, self.public_ids())
        BotMessage.objects.all().delete()

        response = self.client.post('/api/v1/me/peer/', {'institution': "Harvard"},
                                    **auth(self.student))
        self.assertEqual(response.json()['status'], 'pending')
        self.assertEqual(BotMessage.objects.get().telegram_id, 500)

    def test_editing_approved_profile_keeps_it_public(self):
        self.apply()
        peer = Peer.objects.get()
        self.moderate(peer, 'approved')
        BotMessage.objects.all().delete()

        response = self.client.post('/api/v1/me/peer/', {'city': "Cambridge"}, **auth(self.student))
        self.assertEqual(response.json()['status'], 'approved')
        self.assertIn(peer.pk, self.public_ids())
        self.assertFalse(BotMessage.objects.exists())
