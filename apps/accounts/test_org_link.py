"""Tashkilot birinchi kirishda Telegram'ini maxsus bot havolasi orqali ulaydi."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.initiatives.models import Initiative, InitiativeVote, Organization

from .models import TelegramAuthCode, TelegramLink
from .org_link import is_disposable_account

User = get_user_model()

SECRET = 'test-bot-kalit'
PASSWORD = 'Tashkilot2026!'
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'org-link-tests'}}


def make_organization(email='agro@test.uz', name="AgroTech MChJ", telegram_id=None):
    account = User.objects.create_user(
        email=email, password=PASSWORD, full_name="Ali Valiyev",
        phone='+998901112233', role='organization', is_verified=True,
        telegram_id=telegram_id)
    Organization.objects.create(user=account, name=name, sphere='it',
                                contact_person="Ali Valiyev", phone='+998901112233')
    return account


@override_settings(TELEGRAM_API_SECRET=SECRET, TELEGRAM_BOT_USERNAME='samyoshbot')
class OrganizationLinkFlowTests(TestCase):
    def setUp(self):
        self.account = make_organization()
        self.secret = {'HTTP_X_BOT_SECRET': SECRET}

    # ---------------- yordamchilar ----------------

    def login(self, email='agro@test.uz', password=PASSWORD):
        return self.client.post(reverse('api:password_login'),
                                {'email': email, 'password': password},
                                content_type='application/json')

    def status(self, ticket):
        return self.client.post(reverse('api:telegram_link'), {'ticket': ticket},
                                content_type='application/json')

    def bot(self, token, telegram_id=777001, **extra):
        return self.client.post(reverse('accounts:bot_org_link'),
                                {'token': token, 'telegram_id': telegram_id, **extra},
                                content_type='application/json', **self.secret).json()

    def start(self):
        data = self.login().json()
        token = data['bot_url'].split('start=org_', 1)[1]
        return data, token

    # ---------------- birinchi kirish ----------------

    def test_first_password_login_asks_for_telegram_instead_of_tokens(self):
        response = self.login()
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['telegram_required'])
        self.assertNotIn('access', data)
        self.assertEqual(data['organization'], "AgroTech MChJ")
        self.assertTrue(data['first_login'])
        self.assertTrue(data['bot_url'].startswith('https://t.me/samyoshbot?start=org_'))
        # Telegram start parametri: 64 belgigacha, faqat harf, raqam, _ va -
        payload = data['bot_url'].split('start=', 1)[1]
        self.assertLessEqual(len(payload), 64)
        self.assertRegex(payload, r'^[A-Za-z0-9_-]+$')

    def test_wrong_password_still_rejected(self):
        self.assertEqual(self.login(password='xato').status_code, 401)
        self.assertFalse(TelegramLink.objects.exists())

    def test_full_flow_bot_asks_only_phone_then_site_signs_in(self):
        data, token = self.start()
        self.assertEqual(self.status(data['ticket']).json()['status'], 'waiting')

        # Bot havolani ochdi: tashkilot tanildi, faqat raqam so'raladi
        opened = self.bot(token)
        self.assertEqual(opened, {'ok': False, 'error': 'need_phone',
                                  'organization': "AgroTech MChJ"})
        self.assertEqual(self.status(data['ticket']).json()['status'], 'phone')

        # Raqam keldi — ulandi
        done = self.bot(token, phone='998 93 555 44 33', username='agro_admin')
        self.assertEqual(done, {'ok': True, 'organization': "AgroTech MChJ"})

        self.account.refresh_from_db()
        self.assertEqual(self.account.telegram_id, 777001)
        self.assertEqual(self.account.telegram_username, 'agro_admin')
        self.assertEqual(self.account.phone, '+998935554433')

        # Brauzer darhol kiradi — token shu javobda
        signed = self.status(data['ticket'])
        self.assertEqual(signed.status_code, 200)
        self.assertEqual(signed.json()['status'], 'linked')
        self.assertIn('access', signed.json())
        self.assertEqual(signed.json()['user']['organization_name'], "AgroTech MChJ")
        self.assertTrue(signed.json()['user']['telegram_linked'])

        # Kalit bir martalik
        self.assertEqual(self.status(data['ticket']).json()['status'], 'used')

        # Keyingi safar parol bilan to'g'ridan-to'g'ri kiradi
        again = self.login().json()
        self.assertIn('access', again)
        self.assertNotIn('telegram_required', again)

    def test_organization_is_not_asked_age_or_district_in_bot(self):
        _, token = self.start()
        self.bot(token)
        self.bot(token, phone='+998935554433')

        # Oddiy /start: tashkilotga darhol kod beriladi
        response = self.client.post(reverse('accounts:telegram_issue_code'),
                                    {'telegram_id': 777001, 'first_name': "Ali"},
                                    HTTP_X_BOT_SECRET=SECRET).json()
        self.assertTrue(response['ok'])
        self.assertEqual(User.objects.filter(role='organization').count(), 1)

    def test_repeated_open_after_linking_says_already_linked(self):
        _, token = self.start()
        self.bot(token)
        self.bot(token, phone='+998935554433')

        self.assertEqual(self.bot(token), {'ok': True, 'organization': "AgroTech MChJ",
                                           'already': True})
        # Boshqa odam o'sha havolani ochsa — yaroqsiz
        self.assertEqual(self.bot(token, telegram_id=999999)['error'], 'bad_link')

    # ---------------- yaroqsiz holatlar ----------------

    def test_unknown_token(self):
        self.assertEqual(self.bot('yoq-bunday'), {'ok': False, 'error': 'bad_link'})
        self.assertEqual(self.status('yoq').status_code, 404)

    def test_expired_link(self):
        data, token = self.start()
        TelegramLink.objects.update(created_at=timezone.now() - timedelta(minutes=16))

        self.assertEqual(self.bot(token)['error'], 'expired')
        self.assertEqual(self.bot(token, phone='+998935554433')['error'], 'expired')
        self.assertEqual(self.status(data['ticket']).json()['status'], 'expired')
        self.account.refresh_from_db()
        self.assertIsNone(self.account.telegram_id)

    def test_new_login_cancels_previous_link(self):
        first, first_token = self.start()
        second, second_token = self.start()

        self.assertEqual(self.bot(first_token)['error'], 'bad_link')
        self.assertEqual(self.status(first['ticket']).status_code, 404)
        self.assertEqual(self.bot(second_token)['error'], 'need_phone')

    def test_telegram_of_active_user_is_not_taken(self):
        youth = User.objects.create_user(email='yosh@test.uz', full_name="Yosh",
                                         role='yosh', telegram_id=777001, age=20)
        Initiative.objects.create(direction='eco', kind='idea', title="G'oya",
                                  description="X", author_name="Yosh", author=youth)

        _, token = self.start()
        self.assertEqual(self.bot(token)['error'], 'telegram_taken')
        self.assertEqual(self.bot(token, phone='+998935554433')['error'], 'telegram_taken')

        youth.refresh_from_db()
        self.assertEqual(youth.telegram_id, 777001)
        self.account.refresh_from_db()
        self.assertIsNone(self.account.telegram_id)

    def test_empty_bot_account_is_replaced_by_organization(self):
        # Xodim avval botga oddiy odam sifatida kirib ko'rgan — hisob bo'sh
        stub = User.objects.create_user(email='tg777001@telegram.local', full_name="Ali",
                                        telegram_id=777001)
        TelegramAuthCode.objects.create(code='123456', user=stub, telegram_id=777001)

        _, token = self.start()
        self.assertEqual(self.bot(token)['error'], 'need_phone')
        self.assertTrue(self.bot(token, phone='+998935554433')['ok'])

        self.assertFalse(User.objects.filter(pk=stub.pk).exists())
        self.account.refresh_from_db()
        self.assertEqual(self.account.telegram_id, 777001)

    def test_organization_already_linked_to_other_telegram(self):
        _, token = self.start()
        User.objects.filter(pk=self.account.pk).update(telegram_id=555)
        self.assertEqual(self.bot(token)['error'], 'org_taken')

    def test_bot_endpoint_needs_secret(self):
        response = self.client.post(reverse('accounts:bot_org_link'), {'token': 'x'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)


class DisposableAccountTests(TestCase):
    def test_empty_account_is_disposable(self):
        user = User.objects.create_user(email='bosh@test.uz', full_name="Bo'sh",
                                        telegram_id=1)
        self.assertTrue(is_disposable_account(user))

    def test_account_with_vote_or_initiative_is_kept(self):
        voter = User.objects.create_user(email='ovoz@test.uz', full_name="Ovoz", telegram_id=2)
        initiative = Initiative.objects.create(direction='eco', kind='idea', title="G'oya",
                                               description="X", author_name="A")
        InitiativeVote.objects.create(initiative=initiative, user=voter)
        self.assertFalse(is_disposable_account(voter))

        author = User.objects.create_user(email='muallif@test.uz', full_name="M", telegram_id=3)
        Initiative.objects.create(direction='eco', kind='idea', title="Boshqa",
                                  description="Y", author_name="M", author=author)
        self.assertFalse(is_disposable_account(author))

    def test_admins_and_organizations_are_never_disposable(self):
        self.assertFalse(is_disposable_account(make_organization()))
        admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")
        self.assertFalse(is_disposable_account(admin))


@override_settings(TELEGRAM_API_SECRET=SECRET)
class OrganizationCountingTests(TestCase):
    """Tashkilot foydalanuvchi sifatida sanalmaydi — alohida turadi."""

    def setUp(self):
        from apps.api.auth_views import tokens_for

        self.admin = User.objects.create_superuser(email='admin@test.uz', password='x',
                                                   full_name="Admin")
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(self.admin)['access']}"}
        self.youth = User.objects.create_user(email='y@test.uz', full_name="Yosh",
                                              role='yosh', district="Urgut tumani")
        self.organization = make_organization(telegram_id=4242)
        self.organization.telegram_username = 'agro'
        self.organization.last_login = timezone.now()   # avval kirgan
        self.organization.save()

    def test_panel_overview_counts_only_site_users(self):
        data = self.client.get('/api/v1/panel/overview/', **self.auth).json()
        users = next(item for item in data['stats'] if item['key'] == 'users')
        self.assertEqual(users['value'], 1)
        self.assertNotIn(self.organization.pk, [row['id'] for row in data['recent_users']])

    def test_panel_users_hide_organizations_unless_asked(self):
        rows = self.client.get('/api/v1/panel/users/', **self.auth).json()['results']
        self.assertNotIn(self.organization.pk, [row['id'] for row in rows])

        only = self.client.get('/api/v1/panel/users/', {'rol': 'organization'},
                               **self.auth).json()['results']
        self.assertEqual([row['id'] for row in only], [self.organization.pk])

    def test_bot_stats_show_organizations_separately(self):
        data = self.client.get(reverse('accounts:bot_stats'),
                               HTTP_X_BOT_SECRET=SECRET).json()
        self.assertEqual(data['users']['total'], 1)
        self.assertEqual(data['organizations'], {'total': 1, 'telegram': 1})

    def test_organizations_receive_bot_posts_and_ads(self):
        """Tashkilot statistikada alohida, lekin xabar va reklamani hamma bilan teng oladi."""
        ids = self.client.get(reverse('accounts:bot_users'),
                              HTTP_X_BOT_SECRET=SECRET).json()['ids']
        self.assertIn(4242, ids)

    def test_panel_shows_and_unlinks_telegram(self):
        org = Organization.objects.get(user=self.organization)
        rows = self.client.get('/api/v1/panel/organizations/', **self.auth).json()['results']
        self.assertTrue(rows[0]['telegram_linked'])
        self.assertEqual(rows[0]['telegram_username'], 'agro')

        response = self.client.delete(f'/api/v1/panel/organizations/{org.pk}/telegram/',
                                      **self.auth)
        self.assertEqual(response.status_code, 200)
        self.organization.refresh_from_db()
        self.assertIsNone(self.organization.telegram_id)

        # Endi parol bilan kirganda yana Telegram so'raladi
        again = self.client.post(reverse('api:password_login'),
                                 {'email': 'agro@test.uz', 'password': PASSWORD},
                                 content_type='application/json').json()
        self.assertTrue(again['telegram_required'])
        self.assertFalse(again['first_login'])


class CodeLoginProtectionTests(TestCase):
    """Bot kodini tanlab topishga urinish cheklanadi."""

    @override_settings(CACHES=LOCMEM)
    def test_too_many_wrong_codes_are_blocked(self):
        from django.core.cache import cache

        from apps.api.auth_views import CODE_FAILURE_LIMIT

        cache.clear()
        url = reverse('api:telegram_login')
        headers = {'HTTP_X_FORWARDED_FOR': '203.0.113.7'}

        for _ in range(CODE_FAILURE_LIMIT):
            response = self.client.post(url, {'code': '000000'},
                                        content_type='application/json', **headers)
            self.assertEqual(response.status_code, 400)

        blocked = self.client.post(url, {'code': '000000'},
                                   content_type='application/json', **headers)
        self.assertEqual(blocked.status_code, 429)

        # Boshqa manzildagi odamga ta'sir qilmaydi
        other = self.client.post(url, {'code': '000000'}, content_type='application/json',
                                 HTTP_X_FORWARDED_FOR='198.51.100.9')
        self.assertEqual(other.status_code, 400)
        cache.clear()

    def test_client_ip_is_last_forwarded_address(self):
        from django.test import RequestFactory

        from apps.api.auth_views import client_ip

        request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='1.1.1.1, 203.0.113.7',
                                       REMOTE_ADDR='172.18.0.5')
        self.assertEqual(client_ip(request), '203.0.113.7')
        self.assertEqual(client_ip(RequestFactory().get('/', REMOTE_ADDR='10.0.0.1')),
                         '10.0.0.1')

    def test_code_can_be_used_only_once(self):
        user = User.objects.create_user(email='k@test.uz', full_name="K", role='yosh',
                                        age=20, district="Urgut tumani", is_verified=True)
        TelegramAuthCode.objects.create(code='654321', user=user, telegram_id=1)
        url = reverse('api:telegram_login')

        self.assertEqual(self.client.post(url, {'code': '654321'},
                                          content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post(url, {'code': '654321'},
                                          content_type='application/json').status_code, 400)
