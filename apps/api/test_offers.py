"""Investitsiya takliflari: yuborish, egaga xabar, qabul qilish, fikr, panel."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import BotMessage
from apps.cabinet.models import Notification
from apps.startups.models import InvestmentOffer, Startup

from .auth_views import tokens_for

User = get_user_model()
SECRET = 'taklif-test-kalit'


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


@override_settings(SITE_URL='https://samarqandyoshlari.uz', TELEGRAM_API_SECRET=SECRET)
class OfferTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='ega@test.uz', full_name="Marjona Ega",
                                              role='startupper', telegram_id=111)
        self.investor = User.objects.create_user(
            email='inv@test.uz', full_name="Ali Investor", phone='+998901112233',
            telegram_id=222, telegram_username='ali_inv')
        self.startup = Startup.objects.create(
            user=self.owner, full_name="Marjona Ega", phone='+998900000000',
            email='ega@test.uz', region='samarqand', name="RainCollect", sphere='it',
            about="Yomg'ir suvi", status='approved')
        self.url = f'/api/v1/startups/{self.startup.pk}/invest/'
        self.form = {'full_name': "Ali Investor", 'phone': '+998 90 111-22-33',
                     'telegram': 'https://t.me/ali_inv'}

    def send(self, user=None, **changes):
        return self.client.post(self.url, {**self.form, **changes},
                                content_type='application/json', **auth(user or self.investor))

    def accept(self, offer, action='accept', user=None):
        return self.client.post(f'/api/v1/me/offers/{offer.pk}/', {'action': action},
                                content_type='application/json', **auth(user or self.owner))

    def me(self, user):
        return self.client.get('/api/v1/auth/me/', **auth(user)).json()

    # --- Yuborish ---

    def test_guest_must_log_in(self):
        # Holatni mehmon ham so'ray oladi — tugma uni kirish sahifasiga yuboradi
        self.assertEqual(self.client.get(self.url).json(), {'authenticated': False})
        self.assertEqual(self.client.post(self.url, self.form).status_code, 401)

    def test_form_is_prefilled_from_account(self):
        data = self.client.get(self.url, **auth(self.investor)).json()
        self.assertEqual(data, {
            'authenticated': True, 'is_owner': False, 'offer': None,
            'prefill': {'full_name': "Ali Investor", 'phone': '+998901112233',
                        'telegram': 'ali_inv'},
        })
        self.assertTrue(self.client.get(self.url, **auth(self.owner)).json()['is_owner'])

    def test_offer_reaches_owner_on_site_and_in_bot(self):
        response = self.send()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['offer']['status'], 'new')

        offer = InvestmentOffer.objects.get()
        self.assertEqual((offer.investor, offer.phone, offer.telegram),
                         (self.investor, '+998901112233', 'ali_inv'))

        note = Notification.objects.get(user=self.owner)
        self.assertEqual(note.link, '/kabinet/investitsiya')
        self.assertIn("Ali Investor", note.message)
        self.assertEqual(self.me(self.owner)['unread_notifications'], 1)

        message = BotMessage.objects.get()
        self.assertEqual(message.telegram_id, 111)
        for part in ("RainCollect", "Ali Investor", "+998901112233", "@ali_inv"):
            self.assertIn(part, message.text)
        self.assertEqual([button['url'] for button in message.buttons],
                         ['https://t.me/ali_inv',
                          'https://samarqandyoshlari.uz/kabinet/investitsiya'])

    def test_telegram_is_optional_and_text_is_escaped(self):
        self.send(full_name="<b>Ali</b>", telegram='')
        message = BotMessage.objects.get()
        self.assertIn("&lt;b&gt;Ali&lt;/b&gt;", message.text)
        self.assertEqual(len(message.buttons), 1)

    def test_bad_input_is_rejected(self):
        self.assertEqual(self.send(phone='12').status_code, 400)
        self.assertEqual(self.send(telegram='bu username emas').status_code, 400)
        self.assertEqual(self.send(full_name='A').status_code, 400)
        self.assertFalse(InvestmentOffer.objects.exists())

    def test_own_hidden_and_repeated_offers(self):
        self.assertEqual(self.send(user=self.owner).status_code, 400)

        self.assertEqual(self.send().status_code, 201)
        again = self.send()
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()['offer']['status'], 'new')
        self.assertEqual(InvestmentOffer.objects.count(), 1)

        Startup.objects.update(is_public=False)
        self.assertEqual(self.client.get(self.url, **auth(self.investor)).status_code, 404)

    def test_daily_limit(self):
        from .offer_views import DAILY_LIMIT

        for index in range(DAILY_LIMIT):
            other = Startup.objects.create(
                full_name="X", phone='1', email='x@test.uz', region='samarqand',
                name=f"S{index}", sphere='it', about="…", status='approved')
            InvestmentOffer.objects.create(startup=other, investor=self.investor,
                                           full_name="Ali", phone='+998901112233')
        self.assertEqual(self.send().status_code, 429)

    # --- Ega javobi ---

    def test_owner_accepts_and_investor_is_told(self):
        self.send()
        offer = InvestmentOffer.objects.get()
        BotMessage.objects.all().delete()

        stranger = User.objects.create_user(email='z@test.uz', full_name="Begona")
        self.assertEqual(self.accept(offer, user=stranger).status_code, 404)
        self.assertEqual(self.accept(offer, user=self.investor).status_code, 404)
        self.assertEqual(self.accept(offer, action='boshqa').status_code, 400)

        data = self.accept(offer).json()
        self.assertEqual((data['status'], data['phone']), ('accepted', '+998901112233'))
        offer.refresh_from_db()
        self.assertIsNotNone(offer.responded_at)
        self.assertGreater(offer.feedback_ask_after, timezone.now())

        self.assertEqual(Notification.objects.get(user=self.investor).title,
                         "Taklifingiz qabul qilindi")
        message = BotMessage.objects.get()
        self.assertEqual(message.telegram_id, 222)
        self.assertIn("RainCollect", message.text)

        # Ikkinchi marta bosilsa — qayta xabar ketmaydi
        self.accept(offer)
        self.assertEqual(BotMessage.objects.count(), 1)

    def test_decline_tells_investor_only_on_site(self):
        self.send()
        BotMessage.objects.all().delete()
        self.assertEqual(self.accept(InvestmentOffer.objects.get(), 'decline').json()['status'],
                         'declined')
        self.assertTrue(Notification.objects.filter(user=self.investor).exists())
        self.assertFalse(BotMessage.objects.exists())

    # --- Fikr ---

    def test_feedback_is_asked_later_and_saved(self):
        self.send()
        offer = InvestmentOffer.objects.get()
        feedback_url = f'/api/v1/me/offers/{offer.pk}/fikr/'
        post = lambda body: self.client.post(feedback_url, body,           # noqa: E731
                                             content_type='application/json', **auth(self.owner))

        # Qabul qilinmagan taklif haqida fikr so'ralmaydi
        self.assertEqual(post({'outcome': 'deal'}).status_code, 400)
        self.accept(offer)

        # Darhol emas — biroz o'tib so'raladi
        self.assertIsNone(self.me(self.owner)['pending_feedback'])
        InvestmentOffer.objects.update(feedback_ask_after=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.me(self.owner)['pending_feedback'], {
            'id': offer.pk, 'startup_name': "RainCollect", 'investor_name': "Ali Investor",
            'follow_up': False})
        self.assertIsNone(self.me(self.investor)['pending_feedback'])

        # «Keyinroq» — ikki kunga suriladi
        self.assertEqual(post({'later': True}).status_code, 200)
        self.assertIsNone(self.me(self.owner)['pending_feedback'])

        self.assertEqual(post({'outcome': 'bilmadim'}).status_code, 400)

        # Muzokara davom etmoqda — bir haftadan keyin yakuni so'raladi
        data = post({'outcome': 'talking', 'feedback': "Ikkinchi uchrashuv belgilandi"}).json()
        self.assertEqual((data['outcome'], data['outcome_display']),
                         ('talking', "Muzokara davom etmoqda"))
        offer.refresh_from_db()
        self.assertGreater(offer.feedback_ask_after, timezone.now() + timedelta(days=6))
        InvestmentOffer.objects.update(feedback_ask_after=timezone.now() - timedelta(minutes=1))
        self.assertTrue(self.me(self.owner)['pending_feedback']['follow_up'])

        post({'outcome': 'deal', 'feedback': "Kelishdik"})
        offer.refresh_from_db()
        self.assertEqual((offer.outcome, offer.feedback, offer.feedback_ask_after),
                         ('deal', "Kelishdik", None))
        self.assertIsNone(self.me(self.owner)['pending_feedback'])

        # Begona odam fikr yoza olmaydi
        self.assertEqual(self.client.post(feedback_url, {'outcome': 'deal'},
                                          content_type='application/json',
                                          **auth(self.investor)).status_code, 404)

    # --- Kabinet ---

    def test_cabinet_lists_received_and_sent(self):
        self.send()
        owner = self.client.get('/api/v1/me/offers/', **auth(self.owner)).json()
        self.assertEqual((owner['new'], len(owner['received']), owner['sent']), (1, 1, []))
        row = owner['received'][0]
        self.assertEqual((row['phone'], row['telegram'], row['investor']['id']),
                         ('+998901112233', 'ali_inv', self.investor.pk))
        self.assertEqual(
            self.client.get('/api/v1/me/overview/', **auth(self.owner)).json()['counts']['offers'],
            1)

        investor = self.client.get('/api/v1/me/offers/', **auth(self.investor)).json()
        self.assertEqual(investor['received'], [])
        self.assertEqual(investor['sent'][0]['startup']['name'], "RainCollect")
        self.assertNotIn('phone', investor['sent'][0])

    # --- Bot navbati ---

    def test_bot_takes_each_message_once(self):
        self.send()
        url, secret = '/api/telegram/xabarlar/', {'HTTP_X_BOT_SECRET': SECRET}
        self.assertEqual(self.client.get(url).status_code, 403)

        first = self.client.get(url, **secret).json()['results']
        self.assertEqual([(row['telegram_id'], len(row['buttons'])) for row in first], [(111, 2)])
        self.assertEqual(self.client.get(url, **secret).json()['results'], [])

        self.client.post(url + 'natija/',
                         {'results': [{'id': first[0]['id'], 'ok': False, 'error': 'bloklagan'}]},
                         content_type='application/json', **secret)
        message = BotMessage.objects.get()
        self.assertEqual((message.delivered, message.error), (False, 'bloklagan'))

    def test_user_without_telegram_gets_only_site_notification(self):
        User.objects.filter(pk=self.owner.pk).update(telegram_id=None)
        self.assertEqual(self.send().status_code, 201)
        self.assertTrue(Notification.objects.filter(user=self.owner).exists())
        self.assertFalse(BotMessage.objects.exists())

    # --- Panel ---

    def test_panel_shows_stats_and_filters(self):
        admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="Admin")
        url = '/api/v1/panel/investitsiya/'
        self.assertEqual(self.client.get(url, **auth(self.investor)).status_code, 404)

        self.send()
        offer = InvestmentOffer.objects.get()
        second = User.objects.create_user(email='i2@test.uz', full_name="Bobur Sarmoya")
        InvestmentOffer.objects.create(startup=self.startup, investor=second,
                                       full_name="Bobur Sarmoya", phone='+998935556677')
        self.accept(offer)
        self.client.post(f'/api/v1/me/offers/{offer.pk}/fikr/',
                         {'outcome': 'deal', 'feedback': "Zo'r"},
                         content_type='application/json', **auth(self.owner))

        data = self.client.get(url, **auth(admin)).json()
        stats = data['stats']
        self.assertEqual(
            (stats['total'], stats['new'], stats['accepted'], stats['feedback'], stats['deals'],
             stats['waiting_feedback'], stats['investors'], stats['startups']),
            (2, 1, 1, 1, 1, 0, 2, 1))
        row = next(item for item in data['results'] if item['id'] == offer.pk)
        self.assertEqual((row['owner']['id'], row['investor']['id'], row['feedback']),
                         (self.owner.pk, self.investor.pk, "Zo'r"))

        names = lambda query: [item['full_name'] for item in                  # noqa: E731
                               self.client.get(url + query, **auth(admin)).json()['results']]
        self.assertEqual(names('?holat=new'), ["Bobur Sarmoya"])
        self.assertEqual(names('?fikr=bor'), ["Ali Investor"])
        self.assertEqual(names('?natija=deal'), ["Ali Investor"])
        self.assertEqual(names('?natija=no_deal'), [])
        self.assertEqual(names('?q=bobur'), ["Bobur Sarmoya"])
        self.assertEqual(len(names('?q=raincollect')), 2)

        self.assertEqual(
            self.client.delete(f'{url}{offer.pk}/', **auth(admin)).status_code, 200)
        self.assertEqual(InvestmentOffer.objects.count(), 1)
