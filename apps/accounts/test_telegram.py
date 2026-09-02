from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TelegramAuthCode

User = get_user_model()

SECRET = 'test-maxfiy-kalit'


@override_settings(TELEGRAM_API_SECRET=SECRET)
class TelegramCodeTests(TestCase):
    """Bot kod beradi -> foydalanuvchi kodni kiritadi -> tizimga kiradi."""

    url = None

    def setUp(self):
        self.api_url = reverse('accounts:telegram_issue_code')
        self.login_url = reverse('accounts:login')

    def _issue(self, secret=SECRET, **overrides):
        data = {
            'telegram_id': 555000111,
            'first_name': "Nodirbek",
            'last_name': "Shukurov",
            'username': "nodirbek",
            'phone': "+998500056821",
        }
        data.update(overrides)
        return self.client.post(self.api_url, data, HTTP_X_BOT_SECRET=secret)

    # ---------------- Bot tomoni ----------------

    def test_bot_gets_code_and_user_is_created(self):
        response = self._issue()
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['created'])
        self.assertEqual(len(payload['code']), 6)

        user = User.objects.get(telegram_id=555000111)
        self.assertEqual(user.full_name, "Nodirbek Shukurov")
        self.assertEqual(user.phone, "+998500056821")
        self.assertTrue(user.is_verified)
        self.assertFalse(user.has_usable_password())

    def test_urlencoded_payload_accepted(self):
        """Bot fayl yubormasa aiohttp urlencoded jo'natadi — u ham qabul qilinadi."""
        response = self.client.post(
            self.api_url,
            'telegram_id=777&first_name=Test&phone=%2B998901112233',
            content_type='application/x-www-form-urlencoded',
            HTTP_X_BOT_SECRET=SECRET,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(telegram_id=777).exists())

    def test_json_payload_accepted(self):
        response = self.client.post(
            self.api_url,
            {'telegram_id': 888, 'first_name': "Json"},
            content_type='application/json',
            HTTP_X_BOT_SECRET=SECRET,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(telegram_id=888).exists())

    def test_wrong_secret_forbidden(self):
        self.assertEqual(self._issue(secret='notogri').status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_missing_telegram_id(self):
        response = self.client.post(self.api_url, {'first_name': "X"},
                                    HTTP_X_BOT_SECRET=SECRET)
        self.assertEqual(response.status_code, 400)

    def test_second_request_reuses_user_and_invalidates_old_code(self):
        first = self._issue().json()['code']
        second = self._issue().json()['code']

        self.assertEqual(User.objects.filter(telegram_id=555000111).count(), 1)
        self.assertNotEqual(first, second)

        old = TelegramAuthCode.objects.get(code=first)
        self.assertIsNotNone(old.used_at)

    def test_existing_phone_is_linked(self):
        existing = User.objects.create_user(email='bor@example.com', password='Samyosh2026!',
                                            full_name="Bor Hisob", phone="+998500056821")
        self._issue()

        existing.refresh_from_db()
        self.assertEqual(existing.telegram_id, 555000111)
        self.assertEqual(User.objects.count(), 1)

    # ---------------- Sayt tomoni ----------------

    def test_login_with_code(self):
        code = self._issue().json()['code']

        response = self.client.post(self.login_url, {'code': code})
        self.assertRedirects(response, reverse('cabinet:dashboard'))
        self.assertEqual(self.client.get(reverse('cabinet:dashboard')).status_code, 200)

    def test_code_works_once(self):
        code = self._issue().json()['code']
        self.client.post(self.login_url, {'code': code})
        self.client.post(reverse('accounts:logout'))

        response = self.client.post(self.login_url, {'code': code})
        self.assertContains(response, "allaqachon ishlatilgan")

    def test_expired_code_rejected(self):
        code = self._issue().json()['code']
        entry = TelegramAuthCode.objects.get(code=code)
        entry.created_at = timezone.now() - timezone.timedelta(minutes=10)
        entry.save(update_fields=['created_at'])

        response = self.client.post(self.login_url, {'code': code})
        self.assertContains(response, "eskirgan")

    def test_unknown_code_rejected(self):
        response = self.client.post(self.login_url, {'code': '000000'})
        self.assertContains(response, "topilmadi")

    def test_non_digit_code_rejected(self):
        response = self.client.post(self.login_url, {'code': 'abcdef'})
        self.assertContains(response, "faqat raqamlardan")

    def test_login_page_has_bot_link(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "t.me/")
        self.assertContains(response, "Kodni kiriting")

    def test_no_password_form_on_site(self):
        """Parol bilan kirish butunlay olib tashlangan."""
        response = self.client.get(self.login_url)
        self.assertNotContains(response, 'type="password"')

    def test_register_url_redirects_to_login(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertRedirects(response, self.login_url)

    def test_logged_in_user_redirected(self):
        code = self._issue().json()['code']
        self.client.post(self.login_url, {'code': code})

        response = self.client.get(self.login_url)
        self.assertRedirects(response, reverse('cabinet:dashboard'))


@override_settings(TELEGRAM_API_SECRET=SECRET)
class PhoneMatchingTests(TestCase):
    """Telegram raqamni har xil ko'rinishda yuborishi mumkin."""

    def setUp(self):
        self.api_url = reverse('accounts:telegram_issue_code')
        self.admin = User.objects.create_superuser(
            email='admin@samyosh.uz', password='Samyosh2026!',
            full_name="Bosh Admin", phone="+998500056821",
        )

    def _issue(self, phone):
        return self.client.post(
            self.api_url,
            {'telegram_id': 999888777, 'first_name': "Test", 'phone': phone},
            HTTP_X_BOT_SECRET=SECRET,
        )

    def test_phone_without_plus_matches(self):
        """Telegram ko'pincha `+` siz yuboradi."""
        response = self._issue('998500056821')

        self.assertFalse(response.json()['created'])
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.telegram_id, 999888777)
        self.assertEqual(User.objects.count(), 1)

    def test_phone_with_spaces_matches(self):
        self._issue('+998 50 005 68 21')

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.telegram_id, 999888777)
        self.assertEqual(User.objects.count(), 1)

    def test_admin_keeps_rights_after_telegram_login(self):
        """Mavjud admin Telegram orqali kirsa — huquqlari saqlanadi."""
        code = self._issue('998500056821').json()['code']
        self.client.post(reverse('accounts:login'), {'code': code})

        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 200)

    def test_new_telegram_user_is_not_admin(self):
        """Yangi odam Telegram orqali kirsa — oddiy foydalanuvchi bo'ladi."""
        response = self.client.post(
            self.api_url,
            {'telegram_id': 111000222, 'first_name': "Begona", 'phone': '998901112233'},
            HTTP_X_BOT_SECRET=SECRET,
        )
        self.assertTrue(response.json()['created'])

        newcomer = User.objects.get(telegram_id=111000222)
        self.assertFalse(newcomer.is_superuser)
        self.assertFalse(newcomer.is_staff)
        self.assertEqual(newcomer.role, 'entrepreneur')

        code = response.json()['code']
        self.client.post(reverse('accounts:login'), {'code': code})
        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 404)

    def test_phone_stored_normalized(self):
        self.client.post(
            self.api_url,
            {'telegram_id': 555, 'first_name': "Yangi", 'phone': '998 90 111 22 33'},
            HTTP_X_BOT_SECRET=SECRET,
        )
        self.assertEqual(User.objects.get(telegram_id=555).phone, '+998901112233')
