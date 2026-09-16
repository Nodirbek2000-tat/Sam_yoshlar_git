"""Bot uchun API: adminlik, statistika, majburiy kanallar va reklama."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.initiatives.models import Initiative

from .models import Broadcast, ChannelJoin, RequiredChannel

User = get_user_model()

SECRET = 'test-bot-kalit'


@override_settings(TELEGRAM_API_SECRET=SECRET)
class BotApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='bosh@test.uz', password='x', full_name="Bosh Admin", telegram_id=111)
        self.youth = User.objects.create_user(
            email='yosh@test.uz', full_name="Yosh", role='yosh', telegram_id=222, age=20)
        self.secret = {'HTTP_X_BOT_SECRET': SECRET}

    # ---------------- Adminlik ----------------

    def test_only_site_admin_is_bot_admin(self):
        url = reverse('accounts:bot_admin_check')
        self.assertTrue(self.client.get(url, {'telegram_id': 111}, **self.secret).json()['is_admin'])
        self.assertFalse(self.client.get(url, {'telegram_id': 222}, **self.secret).json()['is_admin'])
        self.assertFalse(self.client.get(url, {'telegram_id': 999}, **self.secret).json()['is_admin'])

    def test_secret_is_required(self):
        self.assertEqual(self.client.get(reverse('accounts:bot_stats')).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('accounts:bot_stats'),
                            HTTP_X_BOT_SECRET='notogri').status_code, 403)

    # ---------------- Statistika ----------------

    def test_stats_counts_users_and_site(self):
        Initiative.objects.create(direction='eco', kind='idea', title="G'oya",
                                  description="X", author_name="A", vote_count=7)
        channel = RequiredChannel.objects.create(chat_id=-100123, title="Kanal", username='kanal')
        ChannelJoin.objects.create(channel=channel, telegram_id=222)

        data = self.client.get(reverse('accounts:bot_stats'), **self.secret).json()
        self.assertEqual(data['users']['bot'], 1)          # admin sanalmaydi
        self.assertEqual(data['site']['initiatives'], 1)
        self.assertEqual(data['site']['votes'], 7)
        self.assertEqual(data['channels'][0]['joined'], 1)
        self.assertEqual(data['channels'][0]['link'], 'https://t.me/kanal')

    # ---------------- Kanallar ----------------

    def test_channel_add_update_and_delete(self):
        url = reverse('accounts:bot_channels')
        response = self.client.post(url, {'chat_id': -100500, 'title': "Yangi kanal",
                                          'username': '@yangi', 'added_by': 111},
                                    content_type='application/json', **self.secret)
        self.assertTrue(response.json()['created'])
        channel_id = response.json()['channel']['id']
        self.assertEqual(RequiredChannel.objects.get().username, 'yangi')

        # Ikkinchi marta — yangisi yaratilmaydi, mavjudi yangilanadi
        again = self.client.post(url, {'chat_id': -100500, 'title': "Nomi o'zgardi"},
                                 content_type='application/json', **self.secret)
        self.assertFalse(again.json()['created'])
        self.assertEqual(RequiredChannel.objects.count(), 1)

        detail = reverse('accounts:bot_channel_detail', args=[channel_id])
        off = self.client.post(detail, {'is_active': False},
                               content_type='application/json', **self.secret)
        self.assertFalse(off.json()['channel']['is_active'])

        self.assertTrue(self.client.delete(detail, **self.secret).json()['deleted'])
        self.assertFalse(RequiredChannel.objects.exists())

    def test_only_active_channels_are_required(self):
        RequiredChannel.objects.create(chat_id=-1, title="Faol")
        RequiredChannel.objects.create(chat_id=-2, title="O'chiq", is_active=False)

        rows = self.client.get(reverse('accounts:bot_channels'), {'faqat_faol': '1'},
                               **self.secret).json()['results']
        self.assertEqual([row['title'] for row in rows], ["Faol"])

    def test_joins_are_counted_once(self):
        channel = RequiredChannel.objects.create(chat_id=-100777, title="Kanal")
        url = reverse('accounts:bot_channel_joins')
        payload = {'telegram_id': 222, 'chat_ids': [-100777, -100999]}

        first = self.client.post(url, payload, content_type='application/json', **self.secret)
        self.assertEqual(first.json()['added'], 1)          # ikkinchi kanal bazada yo'q

        second = self.client.post(url, payload, content_type='application/json', **self.secret)
        self.assertEqual(second.json()['added'], 0)         # takrorlanmaydi
        self.assertEqual(channel.joins.count(), 1)

    # ---------------- Reklama ----------------

    def test_user_ids_for_broadcast(self):
        data = self.client.get(reverse('accounts:bot_users'), **self.secret).json()
        self.assertEqual(sorted(data['ids']), [111, 222])

    def test_broadcast_is_recorded_with_result(self):
        start = self.client.post(reverse('accounts:bot_broadcast'), {
            'text': "Yangi grant e'lon qilindi",
            'kind': 'photo',
            'file_id': 'AgACAgIAAx',
            'buttons': [{'label': "Batafsil", 'url': 'https://mentadbirkor.uz'}],
            'total': 2,
            'created_by': 111,
        }, content_type='application/json', **self.secret)
        broadcast_id = start.json()['id']

        result = self.client.post(
            reverse('accounts:bot_broadcast_result', args=[broadcast_id]),
            {'sent': 1, 'failed': 0, 'blocked': 1},
            content_type='application/json', **self.secret)

        self.assertEqual(result.json()['sent'], 1)
        item = Broadcast.objects.get(pk=broadcast_id)
        self.assertEqual(item.buttons[0]['url'], 'https://mentadbirkor.uz')
        self.assertEqual(item.blocked, 1)
        self.assertIsNotNone(item.finished_at)
