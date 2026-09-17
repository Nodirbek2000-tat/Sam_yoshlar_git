"""Bot uchun API: adminlik, statistika, majburiy kanallar va reklama."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.initiatives.models import Initiative

from .models import BotPost, BotSetting, Broadcast, ChannelJoin, RequiredChannel

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
            'buttons': [{'label': "Batafsil", 'url': 'https://samarqandyoshlari.uz'}],
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
        self.assertEqual(item.buttons[0]['url'], 'https://samarqandyoshlari.uz')
        self.assertEqual(item.blocked, 1)
        self.assertIsNotNone(item.finished_at)


@override_settings(TELEGRAM_API_SECRET=SECRET, SITE_URL='https://samarqandyoshlari.uz')
class BotFeedTests(TestCase):
    """Saytga yangi narsa qo'shilsa — botga yuborish navbatiga tushadi."""

    def setUp(self):
        self.secret = {'HTTP_X_BOT_SECRET': SECRET}
        BotSetting.objects.all().delete()

    def _news(self, title="Yangi grant e'lon qilindi"):
        from apps.content.models import News, NewsCategory
        return News.objects.create(
            title=title, excerpt="Yoshlar uchun yangi imkoniyat ochildi.",
            body="Batafsil ma'lumot.", category=NewsCategory.values[0], is_published=True)

    def test_nothing_is_queued_while_disabled(self):
        self._news()
        self.assertEqual(BotPost.objects.count(), 0)

    def test_news_is_queued_when_enabled(self):
        setting = BotSetting.load()
        setting.auto_post = True
        setting.save()

        news = self._news()
        post = BotPost.objects.get()
        self.assertEqual(post.kind, BotPost.Kind.NEWS)
        self.assertEqual(post.object_id, news.pk)
        self.assertEqual(post.link, f"https://samarqandyoshlari.uz/yangiliklar/{news.slug}")
        self.assertEqual(post.status, BotPost.Status.PENDING)

        # Tahrirlansa ham ikkinchi marta navbatga tushmaydi
        news.title = "Sarlavha o'zgardi"
        news.save()
        self.assertEqual(BotPost.objects.count(), 1)

    def test_bot_takes_pending_and_reports_result(self):
        setting = BotSetting.load()
        setting.auto_post = True
        setting.save()
        self._news()

        rows = self.client.get(reverse('accounts:bot_posts'), **self.secret).json()['results']
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['link'].endswith('/yangiliklar/yangi-grant-elon-qilindi'))

        result = self.client.post(
            reverse('accounts:bot_post_result', args=[rows[0]['id']]),
            {'total': 10, 'sent': 9, 'failed': 1},
            content_type='application/json', **self.secret)
        self.assertEqual(result.json()['sent'], 9)

        post = BotPost.objects.get()
        self.assertEqual(post.status, BotPost.Status.SENT)
        # Yuborilgani ikkinchi marta navbatda chiqmaydi
        self.assertEqual(
            self.client.get(reverse('accounts:bot_posts'), **self.secret).json()['results'], [])


class PanelBotTests(TestCase):
    """Paneldagi yoqish/o'chirish tugmasi."""

    def setUp(self):
        from apps.api.auth_views import tokens_for
        self.admin = User.objects.create_superuser(email='panelbot@test.uz', password='x',
                                                   full_name="Admin")
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(self.admin)['access']}"}

    def test_toggle_and_list(self):
        data = self.client.get('/api/v1/panel/bot/', **self.auth).json()
        self.assertFalse(data['auto_post'])

        response = self.client.post('/api/v1/panel/bot/', {'auto_post': True},
                                    content_type='application/json', **self.auth)
        self.assertTrue(response.json()['auto_post'])
        self.assertTrue(BotSetting.load().auto_post)

    def test_regular_user_cannot_open(self):
        from apps.api.auth_views import tokens_for
        user = User.objects.create_user(email='oddiy2@test.uz', full_name="Oddiy")
        auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}
        self.assertEqual(self.client.get('/api/v1/panel/bot/', **auth).status_code, 404)
