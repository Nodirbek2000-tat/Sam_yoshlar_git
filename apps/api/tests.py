import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.api.auth_views import tokens_for
from apps.business.models import BusinessProfile, GalleryImage
from apps.content.models import News
from apps.core.constants import Status
from apps.initiatives.models import (Initiative, InitiativeVote, Organization,
                                     Problem, Solution, SolutionLike)
from apps.startups.models import Startup

User = get_user_model()


class ApiSmokeTests(TestCase):
    def setUp(self):
        self.idea = Initiative.objects.create(
            direction='eco', kind='idea', title="Test g'oya",
            description="Tavsif", author_name="Aziz", vote_count=3,
        )

    def test_public_endpoints(self):
        for path in ['/api/v1/overview/', '/api/v1/reference/', '/api/v1/directions/',
                     '/api/v1/news/', '/api/v1/events/', '/api/v1/announcements/',
                     '/api/v1/initiatives/', '/api/v1/problems/', '/api/v1/peers/',
                     '/api/v1/startups/', '/api/v1/auth/info/']:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200, f"{path} -> {r.status_code}")
                self.assertEqual(r['Content-Type'].split(';')[0], 'application/json')

    def test_directions_have_scene_data(self):
        rows = self.client.get('/api/v1/directions/').json()
        self.assertEqual(len(rows), 14)
        first = rows[0]
        for key in ['id', 'scene', 'name', 'color', 'accent', 'max', 'unit', 'icon', 'votes']:
            self.assertIn(key, first)

    def test_initiative_detail(self):
        data = self.client.get(f'/api/v1/initiatives/{self.idea.pk}/').json()
        self.assertEqual(data['title'], "Test g'oya")
        self.assertEqual(data['vote_count'], 3)
        self.assertIn('direction_info', data)
        self.assertIn('comments', data)
        self.assertFalse(data['voted'])

    def test_guest_cannot_vote(self):
        r = self.client.post(f'/api/v1/initiatives/{self.idea.pk}/vote/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(InitiativeVote.objects.count(), 0)

    def test_telegram_login_bad_code(self):
        r = self.client.post('/api/v1/auth/telegram/', {'code': '000000'})
        self.assertEqual(r.status_code, 400)

    def test_jwt_flow_and_vote(self):
        from apps.accounts.models import TelegramAuthCode
        user = User.objects.create_user(email='a@b.uz', password='X', full_name="Aziz Aliyev")
        TelegramAuthCode.objects.create(code='123456', user=user, telegram_id=1)

        r = self.client.post('/api/v1/auth/telegram/', {'code': '123456'})
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertIn('access', body)
        self.assertEqual(body['user']['full_name'], "Aziz Aliyev")

        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + body['access']}

        me = self.client.get('/api/v1/auth/me/', **auth)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['email'], 'a@b.uz')

        vote = self.client.post(f'/api/v1/initiatives/{self.idea.pk}/vote/', **auth)
        self.assertEqual(vote.status_code, 200, vote.content)
        self.assertEqual(vote.json()['votes'], 4)

        again = self.client.post(f'/api/v1/initiatives/{self.idea.pk}/vote/', **auth)
        self.assertEqual(again.status_code, 409)

    def test_code_cannot_be_reused(self):
        from apps.accounts.models import TelegramAuthCode
        user = User.objects.create_user(email='c@d.uz', password='X', full_name="B")
        TelegramAuthCode.objects.create(code='222222', user=user, telegram_id=2)
        self.assertEqual(self.client.post('/api/v1/auth/telegram/', {'code': '222222'}).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/telegram/', {'code': '222222'}).status_code, 400)

    def test_role_selection(self):
        from apps.accounts.models import TelegramAuthCode
        user = User.objects.create_user(email='e@f.uz', password='X', full_name="C")
        TelegramAuthCode.objects.create(code='333333', user=user, telegram_id=3)
        body = self.client.post('/api/v1/auth/telegram/', {'code': '333333'}).json()
        self.assertTrue(body['needs_profile'])

        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + body['access']}
        r = self.client.patch('/api/v1/auth/me/',
                              {'role': 'startupper', 'region': 'samarqand'},
                              content_type='application/json', **auth)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['role'], 'startupper')
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    def test_admin_role_rejected(self):
        from apps.accounts.models import TelegramAuthCode
        user = User.objects.create_user(email='g@h.uz', password='X', full_name="D")
        TelegramAuthCode.objects.create(code='444444', user=user, telegram_id=4)
        body = self.client.post('/api/v1/auth/telegram/', {'code': '444444'}).json()
        auth = {'HTTP_AUTHORIZATION': 'Bearer ' + body['access']}
        r = self.client.patch('/api/v1/auth/me/', {'role': 'admin'},
                              content_type='application/json', **auth)
        self.assertEqual(r.status_code, 400)
        user.refresh_from_db()
        self.assertNotEqual(user.role, 'admin')


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK,
                                   'DEFAULT_THROTTLE_RATES': {'login': '1000/min'}})
class PasswordLoginTests(TestCase):
    """Login va parol — faqat qo'lda ochilgan hisoblar (tashkilot, admin) uchun."""

    def setUp(self):
        # Sozlama almashgach eski hisoblagichni tozalaymiz
        cache.clear()
        self.org = User.objects.create_user(
            email='tashkilot@mentadbirkor.uz', password='Parol2026!',
            full_name="Tashkilot", role='organization', is_verified=True,
        )

    def test_login_with_password(self):
        r = self.client.post('/api/v1/auth/login/',
                             {'email': 'tashkilot@mentadbirkor.uz',
                              'password': 'Parol2026!'})
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertIn('access', body)
        self.assertEqual(body['user']['role'], 'organization')
        self.assertFalse(body['needs_profile'])

    def test_email_is_case_insensitive(self):
        r = self.client.post('/api/v1/auth/login/',
                             {'email': 'Tashkilot@Mentadbirkor.UZ',
                              'password': 'Parol2026!'})
        self.assertEqual(r.status_code, 200)

    def test_wrong_password(self):
        r = self.client.post('/api/v1/auth/login/',
                             {'email': 'tashkilot@mentadbirkor.uz',
                              'password': 'xato'})
        self.assertEqual(r.status_code, 401)

    def test_unknown_user_same_message(self):
        """Hisob bor-yo'qligini oshkor qilmaymiz."""
        unknown = self.client.post('/api/v1/auth/login/',
                                   {'email': 'yoq@mentadbirkor.uz', 'password': 'x'})
        wrong = self.client.post('/api/v1/auth/login/',
                                 {'email': 'tashkilot@mentadbirkor.uz', 'password': 'x'})
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(unknown.json()['detail'], wrong.json()['detail'])

    def test_telegram_user_cannot_use_password_login(self):
        """Telegram orqali kelgan hisobda parol yo'q — bu yo'l yopiq."""
        tg = User.objects.create_user(email='tg@mentadbirkor.uz', full_name="TG")
        tg.set_unusable_password()
        tg.save()

        r = self.client.post('/api/v1/auth/login/',
                             {'email': 'tg@mentadbirkor.uz', 'password': ''})
        self.assertEqual(r.status_code, 400)

        r2 = self.client.post('/api/v1/auth/login/',
                              {'email': 'tg@mentadbirkor.uz', 'password': 'nimadir'})
        self.assertEqual(r2.status_code, 401)

    def test_empty_fields(self):
        self.assertEqual(
            self.client.post('/api/v1/auth/login/', {}).status_code, 400)

    def test_token_works_after_password_login(self):
        body = self.client.post('/api/v1/auth/login/',
                                {'email': 'tashkilot@mentadbirkor.uz',
                                 'password': 'Parol2026!'}).json()
        me = self.client.get('/api/v1/auth/me/',
                             HTTP_AUTHORIZATION='Bearer ' + body['access'])
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['email'], 'tashkilot@mentadbirkor.uz')


class PanelApiTests(TestCase):
    """Panel API — faqat adminlar; boshqalarga 404 (403 emas)."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='bosh@mentadbirkor.uz', password='Parol2026!', full_name="Bosh Admin")
        self.plain = User.objects.create_user(
            email='oddiy@mentadbirkor.uz', password='Parol2026!', full_name="Oddiy")
        self.idea = Initiative.objects.create(
            direction='eco', kind='idea', title="G'oya", description="X",
            author_name="A", vote_count=10)

    def _auth(self, user):
        """Login endpointini urmaymiz — u tezlik cheklovi ostida."""
        from apps.api.auth_views import tokens_for
        return {'HTTP_AUTHORIZATION': 'Bearer ' + tokens_for(user)['access']}

    def test_guest_gets_404(self):
        for path in ['/api/v1/panel/overview/', '/api/v1/panel/users/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_plain_user_gets_404(self):
        auth = self._auth(self.plain)
        self.assertEqual(self.client.get('/api/v1/panel/overview/', **auth).status_code, 404)

    def test_admin_sees_overview(self):
        auth = self._auth(self.admin)
        response = self.client.get('/api/v1/panel/overview/', **auth)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('stats', data)
        self.assertIn('pending', data)
        self.assertTrue(any(row['key'] == 'users' for row in data['stats']))

    def test_toggle_admin(self):
        auth = self._auth(self.admin)
        url = f'/api/v1/panel/users/{self.plain.pk}/admin/'

        granted = self.client.post(url, **auth)
        self.assertEqual(granted.status_code, 200)
        self.assertTrue(granted.json()['is_admin'])
        self.plain.refresh_from_db()
        self.assertTrue(self.plain.is_staff)
        self.assertEqual(self.plain.notifications.count(), 1)

        revoked = self.client.post(url, **auth)
        self.assertFalse(revoked.json()['is_admin'])
        self.plain.refresh_from_db()
        self.assertFalse(self.plain.is_staff)

    def test_cannot_change_own_rights(self):
        auth = self._auth(self.admin)
        response = self.client.post(f'/api/v1/panel/users/{self.admin.pk}/admin/', **auth)
        self.assertEqual(response.status_code, 400)

    def test_adjust_votes_delta_and_exact(self):
        auth = self._auth(self.admin)
        url = f'/api/v1/panel/initiatives/{self.idea.pk}/votes/'

        self.assertEqual(
            self.client.post(url, {'delta': 15}, **auth).json()['vote_count'], 25)
        self.assertEqual(
            self.client.post(url, {'exact': 300}, **auth).json()['vote_count'], 300)
        # Manfiyga tushmasin
        self.assertEqual(
            self.client.post(url, {'delta': -1000}, **auth).json()['vote_count'], 0)

    def test_manual_votes_do_not_break_real_voting(self):
        auth = self._auth(self.admin)
        self.client.post(f'/api/v1/panel/initiatives/{self.idea.pk}/votes/',
                         {'exact': 100}, **auth)

        voter = User.objects.create_user(email='ovoz@mentadbirkor.uz',
                                         password='Parol2026!', full_name="Ovoz")
        vote_auth = self._auth(voter)
        result = self.client.post(f'/api/v1/initiatives/{self.idea.pk}/vote/', **vote_auth)
        self.assertEqual(result.json()['votes'], 101)

    def test_list_and_delete(self):
        auth = self._auth(self.admin)

        listing = self.client.get('/api/v1/panel/initiatives/', **auth)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['count'], 1)

        deleted = self.client.delete(
            f'/api/v1/panel/initiatives/{self.idea.pk}/', **auth)
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(Initiative.objects.filter(pk=self.idea.pk).exists())

    def test_unknown_resource_404(self):
        auth = self._auth(self.admin)
        self.assertEqual(self.client.get('/api/v1/panel/nimadir/', **auth).status_code, 404)


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK,
                                   'DEFAULT_THROTTLE_RATES': {'login': '1000/min'}})
class PanelOrganizationTests(TestCase):
    """Korxona kiritish va unga login/parol berish."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            email='panel@mentadbirkor.uz', password='Parol2026!', full_name="Admin")

    def _auth(self):
        from apps.api.auth_views import tokens_for
        return {'HTTP_AUTHORIZATION': 'Bearer ' + tokens_for(self.admin)['access']}

    def test_guest_cannot_see_organizations(self):
        self.assertEqual(self.client.get('/api/v1/panel/organizations/').status_code, 404)

    def test_create_organization_returns_credentials(self):
        response = self.client.post('/api/v1/panel/organizations/', {
            'name': "Samarqand hokimligi",
            'email': 'hokimlik@mentadbirkor.uz',
            'contact_person': "Aziz Rahimov",
            'phone': '+998901112233',
            'sphere': 'davlat',
            'region': 'samarqand',
        }, **self._auth())

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body['name'], "Samarqand hokimligi")

        creds = body['credentials']
        self.assertEqual(creds['email'], 'hokimlik@mentadbirkor.uz')
        self.assertGreaterEqual(len(creds['password']), 10)

        # Berilgan parol bilan haqiqatan kira olishi kerak
        login = self.client.post('/api/v1/auth/login/', {
            'email': creds['email'], 'password': creds['password'],
        })
        self.assertEqual(login.status_code, 200, login.content)
        self.assertEqual(login.json()['user']['role'], 'organization')

    def test_duplicate_email_rejected(self):
        payload = {'name': "Bir", 'email': 'takror@mentadbirkor.uz'}
        self.assertEqual(
            self.client.post('/api/v1/panel/organizations/', payload,
                             **self._auth()).status_code, 201)
        self.assertEqual(
            self.client.post('/api/v1/panel/organizations/', payload,
                             **self._auth()).status_code, 400)

    def test_name_and_email_required(self):
        auth = self._auth()
        self.assertEqual(
            self.client.post('/api/v1/panel/organizations/', {'email': 'a@b.uz'},
                             **auth).status_code, 400)
        self.assertEqual(
            self.client.post('/api/v1/panel/organizations/', {'name': "Nom"},
                             **auth).status_code, 400)

    def test_password_reset_replaces_old_one(self):
        created = self.client.post('/api/v1/panel/organizations/', {
            'name': "Korxona", 'email': 'korxona@mentadbirkor.uz',
        }, **self._auth()).json()

        old_password = created['credentials']['password']

        reset = self.client.post(
            f"/api/v1/panel/organizations/{created['id']}/parol/", **self._auth())
        self.assertEqual(reset.status_code, 200)
        new_password = reset.json()['credentials']['password']
        self.assertNotEqual(old_password, new_password)

        # Eskisi endi ishlamaydi, yangisi ishlaydi
        self.assertEqual(self.client.post('/api/v1/auth/login/', {
            'email': 'korxona@mentadbirkor.uz', 'password': old_password}).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/login/', {
            'email': 'korxona@mentadbirkor.uz', 'password': new_password}).status_code, 200)

    def test_organization_appears_in_list(self):
        self.client.post('/api/v1/panel/organizations/', {
            'name': "Ro'yxatdagi", 'email': 'royxat@mentadbirkor.uz',
        }, **self._auth())

        listing = self.client.get('/api/v1/panel/organizations/', **self._auth()).json()
        self.assertEqual(listing['count'], 1)
        row = listing['results'][0]
        self.assertEqual(row['name'], "Ro'yxatdagi")
        self.assertEqual(row['account_email'], 'royxat@mentadbirkor.uz')
        # Parol ro'yxatda hech qachon qaytmaydi
        self.assertNotIn('password', row)


class SolutionLikeTests(TestCase):
    """Takliflarga layk: bir marta qo'yiladi, qayta bosilsa olinadi,
    ko'p layk yig'gani ro'yxat boshiga chiqadi."""

    def setUp(self):
        self.user = User.objects.create_user(email='yosh@mentadbirkor.uz',
                                             password='Parol12345', full_name="Yosh")
        organization = Organization.objects.create(
            name="Korxona", sphere='it', contact_person="Ali", phone='+998901112233')
        self.problem = Problem.objects.create(
            organization=organization, category='main', description="Muammo",
            is_published=True)

        self.first = Solution.objects.create(
            problem=self.problem, author_name="Birinchi", title="Birinchi yechim",
            description="Tavsif", status=Status.APPROVED)
        self.second = Solution.objects.create(
            problem=self.problem, author_name="Ikkinchi", title="Ikkinchi yechim",
            description="Tavsif", status=Status.APPROVED)

    def _auth(self):
        return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(self.user)['access']}"}

    def test_like_requires_login(self):
        response = self.client.post(f'/api/v1/solutions/{self.first.pk}/like/')
        self.assertEqual(response.status_code, 401)

    def test_like_and_unlike(self):
        url = f'/api/v1/solutions/{self.first.pk}/like/'

        data = self.client.post(url, **self._auth()).json()
        self.assertTrue(data['liked'])
        self.assertEqual(data['like_count'], 1)
        self.assertEqual(SolutionLike.objects.count(), 1)

        data = self.client.post(url, **self._auth()).json()
        self.assertFalse(data['liked'])
        self.assertEqual(data['like_count'], 0)
        self.assertEqual(SolutionLike.objects.count(), 0)

    def test_like_count_never_goes_negative(self):
        # Layk yo'q holatda ham hisob nolda qoladi
        self.client.post(f'/api/v1/solutions/{self.first.pk}/like/', **self._auth())
        self.client.post(f'/api/v1/solutions/{self.first.pk}/like/', **self._auth())
        self.client.post(f'/api/v1/solutions/{self.first.pk}/like/', **self._auth())
        self.first.refresh_from_db()
        self.assertGreaterEqual(self.first.like_count, 0)

    def test_most_liked_solution_comes_first(self):
        self.client.post(f'/api/v1/solutions/{self.second.pk}/like/', **self._auth())

        data = self.client.get(f'/api/v1/problems/{self.problem.pk}/').json()
        titles = [row['title'] for row in data['solutions']]
        self.assertEqual(titles[0], "Ikkinchi yechim")
        self.assertEqual(data['solutions'][0]['like_count'], 1)

    def test_liked_flag_reflects_current_user(self):
        self.client.post(f'/api/v1/solutions/{self.first.pk}/like/', **self._auth())

        # Mehmon uchun hech narsa layk qilinmagan
        guest = self.client.get(f'/api/v1/problems/{self.problem.pk}/').json()
        self.assertFalse(any(row['liked'] for row in guest['solutions']))

        # Layk qo'ygan foydalanuvchi uchun aynan o'sha taklif belgilangan
        mine = self.client.get(f'/api/v1/problems/{self.problem.pk}/', **self._auth()).json()
        liked = {row['title']: row['liked'] for row in mine['solutions']}
        self.assertTrue(liked["Birinchi yechim"])
        self.assertFalse(liked["Ikkinchi yechim"])

    def test_like_notifies_solution_author(self):
        author = User.objects.create_user(email='muallif@mentadbirkor.uz',
                                          password='Parol12345', full_name="Muallif")
        self.first.author = author
        self.first.save(update_fields=['author'])

        self.client.post(f'/api/v1/solutions/{self.first.pk}/like/', **self._auth())
        self.assertEqual(author.notifications.count(), 1)

        # O'ziga o'zi layk bosганda xabar kelmaydi
        own = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(author)['access']}"}
        self.client.post(f'/api/v1/solutions/{self.second.pk}/like/', **own)
        self.second.author = author
        self.second.save(update_fields=['author'])
        self.client.post(f'/api/v1/solutions/{self.second.pk}/like/', **own)
        self.client.post(f'/api/v1/solutions/{self.second.pk}/like/', **own)
        self.assertEqual(author.notifications.count(), 1)

    def test_solution_create_notifies_organization_owner(self):
        owner = User.objects.create_user(email='korxona@mentadbirkor.uz',
                                         password='Parol12345', full_name="Korxona")
        self.problem.organization.user = owner
        self.problem.organization.save(update_fields=['user'])

        response = self.client.post(
            f'/api/v1/problems/{self.problem.pk}/solutions/',
            {'title': "Yangi taklif", 'description': "Tavsif"},
            content_type='application/json', **self._auth())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(owner.notifications.count(), 1)


class RoleChoiceTests(TestCase):
    """Ro'yxatdan o'tgan odam o'zi tanlay oladigan statuslar."""

    def test_reference_offers_self_serve_roles_only(self):
        values = {row['value'] for row in self.client.get('/api/v1/reference/').json()['roles']}
        self.assertEqual(values, {'yosh', 'entrepreneur', 'startupper'})

    def test_user_can_pick_youth_role(self):
        user = User.objects.create_user(email='tanlov@mentadbirkor.uz',
                                        password='Parol12345', full_name="Tanlov")
        auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}

        response = self.client.patch('/api/v1/auth/me/',
                                     {'role': 'yosh', 'full_name': "Tanlov Yosh"},
                                     content_type='application/json', **auth)
        self.assertEqual(response.status_code, 200)

        user.refresh_from_db()
        self.assertEqual(user.role, 'yosh')
        self.assertTrue(user.is_verified)


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK,
                                   'DEFAULT_THROTTLE_RATES': {'login': '1000/min'}})
class PanelNewsTests(TestCase):
    """Panel orqali yangilik qo'shish, tahrirlash va o'chirish."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            email='admin@mentadbirkor.uz', password='Parol12345',
            full_name="Panel Admin")
        self.outsider = User.objects.create_user(
            email='oddiy@mentadbirkor.uz', password='Parol12345', full_name="Oddiy")

    def _auth(self, user=None):
        token = tokens_for(user or self.admin)['access']
        return {'HTTP_AUTHORIZATION': f"Bearer {token}"}

    def _payload(self, **extra):
        data = {
            'title': "Kengash yangi dastur e'lon qildi",
            'category': 'grant',
            'excerpt': "Qisqacha mazmuni.",
            'body': "To'liq matn.",
        }
        data.update(extra)
        return data

    def test_panel_hidden_from_non_admins(self):
        # Mehmon ham, oddiy foydalanuvchi ham panel borligini bilmasin —
        # 403 emas, 404: panel mavjudligi ham oshkor bo'lmasin
        self.assertEqual(self.client.get('/api/v1/panel/news/').status_code, 404)
        self.assertEqual(
            self.client.get('/api/v1/panel/news/', **self._auth(self.outsider)).status_code, 404)

    def test_admin_creates_news(self):
        response = self.client.post('/api/v1/panel/news/', self._payload(),
                                    content_type='application/json', **self._auth())
        self.assertEqual(response.status_code, 201)

        item = News.objects.get()
        self.assertEqual(item.title, "Kengash yangi dastur e'lon qildi")
        self.assertTrue(item.slug)                      # havola o'zi yasaladi
        self.assertEqual(item.author, self.admin)
        self.assertEqual(item.author_name, "Panel Admin")

        # Darhol ochiq API'da ko'rinadi
        public = self.client.get('/api/v1/news/').json()
        self.assertEqual(public['count'], 1)

    def test_short_title_is_rejected(self):
        response = self.client.post('/api/v1/panel/news/', self._payload(title="Ok"),
                                    content_type='application/json', **self._auth())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(News.objects.count(), 0)

    def test_draft_is_hidden_from_public_but_visible_in_panel(self):
        self.client.post('/api/v1/panel/news/', self._payload(is_published=False),
                         content_type='application/json', **self._auth())

        self.assertEqual(self.client.get('/api/v1/news/').json()['count'], 0)
        self.assertEqual(
            self.client.get('/api/v1/panel/news/', **self._auth()).json()['count'], 1)

    def test_admin_edits_and_publishes(self):
        self.client.post('/api/v1/panel/news/', self._payload(is_published=False),
                         content_type='application/json', **self._auth())
        item = News.objects.get()

        response = self.client.patch(f'/api/v1/panel/news/{item.pk}/tahrir/',
                                     {'is_published': True, 'title': "Yangilangan sarlavha"},
                                     content_type='application/json', **self._auth())
        self.assertEqual(response.status_code, 200)

        item.refresh_from_db()
        self.assertTrue(item.is_published)
        self.assertEqual(item.title, "Yangilangan sarlavha")

    def test_admin_deletes_news(self):
        self.client.post('/api/v1/panel/news/', self._payload(),
                         content_type='application/json', **self._auth())
        item = News.objects.get()

        response = self.client.delete(f'/api/v1/panel/news/{item.pk}/', **self._auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(News.objects.count(), 0)

    def test_reference_lists_news_categories(self):
        values = {row['value']
                  for row in self.client.get('/api/v1/reference/').json()['news_categories']}
        self.assertIn('grant', values)
        self.assertIn('forum', values)


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK,
                                   'DEFAULT_THROTTLE_RATES': {'login': '1000/min'}})
class PanelImportTests(TestCase):
    """JSON'dan tashabbuslarni ommaviy yuklash."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            email='import@mentadbirkor.uz', password='Parol12345', full_name="Import Admin")

    def _auth(self, user=None):
        token = tokens_for(user or self.admin)['access']
        return {'HTTP_AUTHORIZATION': f"Bearer {token}"}

    def _payload(self):
        return {'initiatives': [
            {
                'direction': 'eco', 'kind': 'idea',
                'title': "Maktab hovlisiga daraxt",
                'description': "Har bir maktab hovlisiga o'nta ko'chat ekiladi.",
                'expected_result': "Yiliga 300 ta daraxt.",
                'author_name': "Aziz Rahimov", 'region': 'samarqand',
                'vote_count': 287, 'created_at': '2026-05-14',
                'comments': [
                    {'author_name': "Nodira", 'text': "Zo'r fikr.",
                     'created_at': '2026-05-20'},
                    {'author_name': "Bekzod", 'text': "Kim sug'oradi?"},
                ],
            },
            {
                'direction': 'ai', 'kind': 'startup',
                'title': "O'zbek nutq korpusi",
                'description': "Ochiq audio-matn bazasi.",
                'author_name': "Kamola", 'vote_count': 42,
            },
        ]}

    def test_only_admin_can_import(self):
        plain = User.objects.create_user(email='oddiy2@mentadbirkor.uz',
                                         password='Parol12345', full_name="Oddiy")
        self.assertEqual(
            self.client.post('/api/v1/panel/import/initiatives/', self._payload(),
                             content_type='application/json').status_code, 404)
        self.assertEqual(
            self.client.post('/api/v1/panel/import/initiatives/', self._payload(),
                             content_type='application/json',
                             **self._auth(plain)).status_code, 404)

    def test_import_creates_initiatives_with_votes_and_comments(self):
        response = self.client.post('/api/v1/panel/import/initiatives/', self._payload(),
                                    content_type='application/json', **self._auth())
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['created'], 2)
        self.assertEqual(data['comments'], 2)
        self.assertEqual(data['votes'], 329)
        self.assertEqual(data['problems'], [])

        idea = Initiative.objects.get(title="Maktab hovlisiga daraxt")
        self.assertEqual(idea.vote_count, 287)
        self.assertEqual(idea.direction, 'eco')
        self.assertTrue(idea.is_published)
        self.assertEqual(idea.comments.count(), 2)
        # Berilgan sana saqlanadi (mahalliy vaqt bo'yicha tekshiramiz)
        from django.utils import timezone as tz
        self.assertEqual(tz.localtime(idea.created_at).date().isoformat(), '2026-05-14')

    def test_second_import_skips_duplicates(self):
        self.client.post('/api/v1/panel/import/initiatives/', self._payload(),
                         content_type='application/json', **self._auth())
        again = self.client.post('/api/v1/panel/import/initiatives/', self._payload(),
                                 content_type='application/json', **self._auth()).json()

        self.assertEqual(again['created'], 0)
        self.assertEqual(again['skipped'], 2)
        self.assertEqual(Initiative.objects.count(), 2)

    def test_bad_rows_are_reported_not_fatal(self):
        payload = {'initiatives': [
            {'direction': 'yoq', 'title': "Xato", 'description': "X"},
            {'direction': 'eco', 'title': "", 'description': "X"},
            {'direction': 'eco', 'title': "To'g'ri yozuv", 'description': "Tavsif"},
        ]}
        data = self.client.post('/api/v1/panel/import/initiatives/', payload,
                                content_type='application/json', **self._auth()).json()

        self.assertEqual(data['created'], 1)
        self.assertEqual(len(data['problems']), 2)

    def test_rejects_payload_without_initiatives(self):
        response = self.client.post('/api/v1/panel/import/initiatives/', {'boshqa': []},
                                    content_type='application/json', **self._auth())
        self.assertEqual(response.status_code, 400)
        self.assertIn('initiatives', response.json()['detail'])

    def test_organization_file_in_initiatives_section_says_where_to_go(self):
        # Eng ko'p uchraydigan xato: faylni noto'g'ri bo'limga tashlash
        response = self.client.post('/api/v1/panel/import/initiatives/',
                                    {'organizations': [{'name': "AgroTech"}]},
                                    content_type='application/json', **self._auth())

        self.assertEqual(response.status_code, 400)
        self.assertIn("Tashkilotlar", response.json()['detail'])


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK,
                                   'DEFAULT_THROTTLE_RATES': {'login': '1000/min'}})
class PanelOrganizationImportTests(TestCase):
    """Tashkilotlarni muammolari va takliflari bilan yuklash."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            email='orgimport@mentadbirkor.uz', password='Parol12345',
            full_name="Import Admin")

    def _auth(self, user=None):
        token = tokens_for(user or self.admin)['access']
        return {'HTTP_AUTHORIZATION': f"Bearer {token}"}

    def _payload(self):
        return {'organizations': [{
            'name': "AgroTech MChJ",
            'sphere': 'qishloq_xojaligi',
            'contact_person': "Ali Valiyev",
            'phone': '+998901112233',
            'region': 'samarqand',
            'employees': 40,
            'problems': [{
                'category': 'main',
                'description': "Hosilni saqlash uchun sovuq ombor yo'q.",
                'created_at': '2026-04-02',
                'solutions': [
                    {'author_name': "Aziz", 'title': "Quyoshli sovutgich",
                     'description': "Quyosh panelida ishlaydigan modul ombor.",
                     'technologies': "Solar, IoT", 'like_count': 5,
                     'created_at': '2026-04-10'},
                    {'author_name': "Malika", 'title': "Umumiy ombor",
                     'description': "Bir necha fermer birgalikda ijaraga oladi.",
                     'like_count': 2},
                ],
            }],
        }]}

    def test_only_admin_can_import(self):
        plain = User.objects.create_user(email='oddiy3@mentadbirkor.uz',
                                         password='Parol12345', full_name="Oddiy")
        self.assertEqual(
            self.client.post('/api/v1/panel/import/organizations/', self._payload(),
                             content_type='application/json').status_code, 404)
        self.assertEqual(
            self.client.post('/api/v1/panel/import/organizations/', self._payload(),
                             content_type='application/json',
                             **self._auth(plain)).status_code, 404)

    def test_import_creates_organization_problem_and_solutions(self):
        response = self.client.post('/api/v1/panel/import/organizations/', self._payload(),
                                    content_type='application/json', **self._auth())
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['created'], 1)
        self.assertEqual(data['problems_added'], 1)
        self.assertEqual(data['solutions'], 2)
        self.assertEqual(data['likes'], 7)
        self.assertEqual(data['issues'], [])

        organization = Organization.objects.get(name="AgroTech MChJ")
        self.assertEqual(organization.region, 'samarqand')

        problem = organization.problems.get()
        self.assertTrue(problem.is_published)
        self.assertEqual(problem.solutions.count(), 2)

        # Ko'p layk yig'gani ochiq API'da birinchi turadi
        rows = self.client.get(f'/api/v1/problems/{problem.pk}/').json()['solutions']
        self.assertEqual(rows[0]['title'], "Quyoshli sovutgich")
        self.assertEqual(rows[0]['like_count'], 5)

    def test_existing_organization_is_reused_not_duplicated(self):
        self.client.post('/api/v1/panel/import/organizations/', self._payload(),
                         content_type='application/json', **self._auth())
        again = self.client.post('/api/v1/panel/import/organizations/', self._payload(),
                                 content_type='application/json', **self._auth()).json()

        self.assertEqual(again['created'], 0)
        self.assertEqual(again['reused'], 1)
        # Bir xil tavsifli muammo ikkilanmaydi
        self.assertEqual(again['problems_added'], 0)
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(Problem.objects.count(), 1)

    def test_new_problem_is_added_to_existing_organization(self):
        self.client.post('/api/v1/panel/import/organizations/', self._payload(),
                         content_type='application/json', **self._auth())

        payload = self._payload()
        payload['organizations'][0]['problems'] = [{
            'category': 'human', 'description': "Malakali agronom topilmayapti.",
        }]
        data = self.client.post('/api/v1/panel/import/organizations/', payload,
                                content_type='application/json', **self._auth()).json()

        self.assertEqual(data['reused'], 1)
        self.assertEqual(data['problems_added'], 1)
        self.assertEqual(Problem.objects.count(), 2)

    def test_bad_rows_are_reported(self):
        payload = {'organizations': [
            {'name': "", 'sphere': 'it'},
            {'name': "Sohasiz", 'sphere': 'yoq'},
            {'name': "To'g'ri", 'sphere': 'it',
             'problems': [{'category': 'yoq', 'description': "X"}]},
        ]}
        data = self.client.post('/api/v1/panel/import/organizations/', payload,
                                content_type='application/json', **self._auth()).json()

        self.assertEqual(data['created'], 1)
        self.assertEqual(len(data['issues']), 3)

    def test_rejects_payload_without_organizations(self):
        response = self.client.post('/api/v1/panel/import/organizations/', {'boshqa': []},
                                    content_type='application/json', **self._auth())
        self.assertEqual(response.status_code, 400)
        self.assertIn('organizations', response.json()['detail'])

    def test_initiative_file_in_organizations_section_says_where_to_go(self):
        response = self.client.post('/api/v1/panel/import/organizations/',
                                    {'initiatives': [{'title': "G'oya"}]},
                                    content_type='application/json', **self._auth())

        self.assertEqual(response.status_code, 400)
        self.assertIn("Tashabbuslar", response.json()['detail'])


class ProblemAuthoringTests(TestCase):
    """Muammoni faqat tashkilot yozadi; takliflar unga qaytib keladi."""

    def setUp(self):
        self.org_user = User.objects.create_user(
            email='korxona@mentadbirkor.uz', password='Parol12345',
            full_name="Korxona Egasi", role='organization')
        self.organization = Organization.objects.create(
            name="AgroTech", sphere='it', contact_person="Ali",
            phone='+998901112233', user=self.org_user)

        self.youth = User.objects.create_user(
            email='yosh2@mentadbirkor.uz', password='Parol12345',
            full_name="Yosh Tadbirkor", role='yosh')
        self.entrepreneur = User.objects.create_user(
            email='tadbirkor@mentadbirkor.uz', password='Parol12345',
            full_name="Tadbirkor", role='entrepreneur')

    def _auth(self, user):
        return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}

    def _payload(self):
        return {'category': 'main',
                'description': "Hosilni saqlaydigan sovuq ombor yo'q, yozda hosil nobud bo'ladi."}

    def test_guest_cannot_write_problem(self):
        response = self.client.post('/api/v1/problems/yozish/', self._payload(),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_youth_and_entrepreneur_cannot_write_problem(self):
        for user in (self.youth, self.entrepreneur):
            with self.subTest(role=user.role):
                response = self.client.post('/api/v1/problems/yozish/', self._payload(),
                                            content_type='application/json',
                                            **self._auth(user))
                self.assertEqual(response.status_code, 403)
        self.assertEqual(Problem.objects.count(), 0)

    def test_organization_writes_problem_and_it_is_public(self):
        response = self.client.post('/api/v1/problems/yozish/', self._payload(),
                                    content_type='application/json',
                                    **self._auth(self.org_user))
        self.assertEqual(response.status_code, 201)

        problem = Problem.objects.get()
        self.assertEqual(problem.organization, self.organization)
        self.assertTrue(problem.is_published)

        # Darhol ochiq ro'yxatda ko'rinadi
        self.assertEqual(self.client.get('/api/v1/problems/').json()['count'], 1)

    def test_short_description_is_rejected(self):
        response = self.client.post('/api/v1/problems/yozish/',
                                    {'category': 'main', 'description': "Ombor yo'q"},
                                    content_type='application/json',
                                    **self._auth(self.org_user))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Problem.objects.count(), 0)

    def test_organization_sees_its_problems_with_solutions(self):
        self.client.post('/api/v1/problems/yozish/', self._payload(),
                         content_type='application/json', **self._auth(self.org_user))
        problem = Problem.objects.get()

        self.client.post(f'/api/v1/problems/{problem.pk}/solutions/',
                         {'title': "Quyoshli ombor", 'description': "Modul sovutgich."},
                         content_type='application/json', **self._auth(self.youth))

        data = self.client.get('/api/v1/me/problems/', **self._auth(self.org_user)).json()
        self.assertTrue(data['is_organization'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['results'][0]['solutions']), 1)
        self.assertEqual(data['results'][0]['solutions'][0]['title'], "Quyoshli ombor")

    def test_solution_notifies_the_organization(self):
        self.client.post('/api/v1/problems/yozish/', self._payload(),
                         content_type='application/json', **self._auth(self.org_user))
        problem = Problem.objects.get()

        self.client.post(f'/api/v1/problems/{problem.pk}/solutions/',
                         {'title': "Quyoshli ombor", 'description': "Modul sovutgich."},
                         content_type='application/json', **self._auth(self.youth))

        note = self.org_user.notifications.get()
        self.assertIn("taklif", note.title.lower())
        self.assertEqual(note.link, "/kabinet/muammolarim")

    def test_new_solution_is_visible_immediately(self):
        self.client.post('/api/v1/problems/yozish/', self._payload(),
                         content_type='application/json', **self._auth(self.org_user))
        problem = Problem.objects.get()

        response = self.client.post(
            f'/api/v1/problems/{problem.pk}/solutions/',
            {'title': "Quyoshli ombor", 'description': "Modul sovutgich."},
            content_type='application/json', **self._auth(self.youth))
        self.assertEqual(response.status_code, 201)

        # Javobda to'liq taklif qaytadi — front uni ro'yxatga darhol qo'shadi
        created = response.json()
        self.assertEqual(created['title'], "Quyoshli ombor")
        self.assertEqual(created['like_count'], 0)
        self.assertEqual(created['author_name'], "Yosh Tadbirkor")

        # Mehmon ham darrov ko'radi — moderatsiya kutilmaydi
        rows = self.client.get(f'/api/v1/problems/{problem.pk}/').json()['solutions']
        self.assertEqual(len(rows), 1)

    def test_non_organization_gets_empty_problem_list(self):
        data = self.client.get('/api/v1/me/problems/', **self._auth(self.youth)).json()
        self.assertFalse(data['is_organization'])
        self.assertEqual(data['results'], [])

    def test_reference_exposes_problem_questions(self):
        rows = self.client.get('/api/v1/reference/').json()['problem_questions']
        self.assertEqual(len(rows), 10)
        self.assertIn('main', [row['value'] for row in rows])
        self.assertTrue(all(row['label'] for row in rows))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfileSetupTests(TestCase):
    """Ro'yxatdan keyingi ikkinchi qadam: startapper startapini,
    tadbirkor biznesini tanishtiradi. Logotip majburiy — shuning uchun
    anketalar multipart bilan yuboriladi."""

    def setUp(self):
        self.startupper = User.objects.create_user(
            email='startupper@mentadbirkor.uz', password='Parol12345',
            full_name="Startap Egasi", role='startupper', region='samarqand')
        self.entrepreneur = User.objects.create_user(
            email='biznes@mentadbirkor.uz', password='Parol12345',
            full_name="Biznes Egasi", role='entrepreneur', region='buxoro')

    def _auth(self, user):
        return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}

    def test_guest_cannot_send_startup(self):
        response = self.client.post('/api/v1/me/startup/', {'name': "X"},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_startupper_saves_startup(self):
        payload = {
            'name': "Tilchi AI", 'sphere': 'it', 'stage': 'mvp',
            'about': "O'zbek tili uchun ovozli yordamchi — matnni ovozga aylantiradi.",
            'problem_solved': "Ko'zi ojizlar uchun kontent yopiq edi.",
            'team_size': 4,
            'logo': _png('logo.png'),
        }
        response = self.client.post('/api/v1/me/startup/', payload,
                                    **self._auth(self.startupper))
        self.assertEqual(response.status_code, 201)

        startup = Startup.objects.get()
        self.assertEqual(startup.user, self.startupper)
        self.assertEqual(startup.name, "Tilchi AI")
        self.assertEqual(startup.team_size, 4)
        # Hisobdagi ma'lumot o'zi ko'chadi — qayta so'ralmaydi
        self.assertEqual(startup.full_name, "Startap Egasi")
        self.assertEqual(startup.region, 'samarqand')

    def test_second_send_updates_instead_of_duplicating(self):
        payload = {
            'name': "Tilchi AI", 'sphere': 'it', 'stage': 'mvp',
            'about': "O'zbek tili uchun ovozli yordamchi — matnni ovozga aylantiradi.",
        }
        self.client.post('/api/v1/me/startup/', {**payload, 'logo': _png('logo.png')},
                         **self._auth(self.startupper))
        # Ikkinchi yuborishda logo shart emas — avvalgisi saqlanadi
        self.client.post('/api/v1/me/startup/', {**payload, 'name': "Tilchi AI 2.0"},
                         content_type='application/json', **self._auth(self.startupper))

        self.assertEqual(Startup.objects.count(), 1)
        self.assertEqual(Startup.objects.get().name, "Tilchi AI 2.0")

    def test_short_about_is_rejected(self):
        response = self.client.post(
            '/api/v1/me/startup/',
            {'name': "X", 'sphere': 'it', 'stage': 'mvp', 'about': "Qisqa"},
            content_type='application/json', **self._auth(self.startupper))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Startup.objects.count(), 0)

    def test_entrepreneur_saves_business(self):
        payload = {
            'name': "Buxoro Tekstil", 'sphere': 'ishlab_chiqarish',
            'founded_year': 2019, 'employees': 35,
            'description': "Paxtadan trikotaj mahsulot ishlab chiqaramiz va eksport qilamiz.",
            'logo': _png('logo.png'),
        }
        response = self.client.post('/api/v1/me/business/', payload,
                                    **self._auth(self.entrepreneur))
        self.assertEqual(response.status_code, 201)

        profile = BusinessProfile.objects.get()
        self.assertEqual(profile.user, self.entrepreneur)
        self.assertEqual(profile.employees, 35)
        self.assertEqual(profile.region, 'buxoro')

    def test_future_founded_year_is_rejected(self):
        response = self.client.post(
            '/api/v1/me/business/',
            {'name': "X", 'sphere': 'savdo', 'founded_year': 3000,
             'description': "Savdo bilan shug'ullanamiz va eksportga chiqamiz."},
            content_type='application/json', **self._auth(self.entrepreneur))
        self.assertEqual(response.status_code, 400)

    def test_reference_lists_startup_and_business_choices(self):
        data = self.client.get('/api/v1/reference/').json()
        self.assertTrue(data['startup_spheres'])
        self.assertTrue(data['startup_stages'])
        self.assertTrue(data['business_spheres'])


def _png(name='rasm.png', size=(8, 8)):
    """Testlar uchun haqiqiy kichik PNG."""
    import io as _io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = _io.BytesIO()
    Image.new('RGB', size, (40, 160, 120)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OnboardingTests(TestCase):
    """Yangi foydalanuvchi: rol → biznes yoki startap anketasi → tayyor."""

    def _user(self, **extra):
        data = {'email': 'yangi@mentadbirkor.uz', 'password': None, 'full_name': "Yangi User"}
        data.update(extra)
        return User.objects.create_user(**data)

    def _auth(self, user):
        return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}

    def test_steps_follow_the_role(self):
        from apps.api.onboarding import onboarding_step

        user = self._user(is_verified=False)
        self.assertEqual(onboarding_step(user), 'role')

        user.is_verified = True
        user.role = 'entrepreneur'
        self.assertEqual(onboarding_step(user), 'business')

        user.role = 'startupper'
        self.assertEqual(onboarding_step(user), 'startup')

        # Yoshdan qayerda o'qishi so'raladi; chet elda bo'lsa — rasmli anketa
        user.role = 'yosh'
        self.assertEqual(onboarding_step(user), 'study')

        user.study_location = 'abroad'
        self.assertEqual(onboarding_step(user), 'peer')

        user.study_location = 'uz'
        self.assertIsNone(onboarding_step(user))

        # Tashkilot va admin hisobini biz ochamiz — ulardan so'ralmaydi
        user.role = 'organization'
        self.assertIsNone(onboarding_step(user))

    def test_me_reports_pending_step(self):
        user = self._user(is_verified=True, role='entrepreneur')
        data = self.client.get('/api/v1/auth/me/', **self._auth(user)).json()
        self.assertEqual(data['onboarding'], 'business')

    def test_business_with_logo_completes_onboarding(self):
        user = self._user(is_verified=True, role='entrepreneur', phone='+998901112233')

        response = self.client.post('/api/v1/me/business/', {
            'name': "Buxoro Tekstil",
            'sphere': 'ishlab_chiqarish',
            'founded_year': '2019',
            'employees': '35',
            'description': "Paxtadan mato ishlab chiqaramiz va eksport qilamiz.",
            'website': 'buxorotekstil.uz',
            'instagram': '@buxorotekstil',
            'logo': _png('logo.png'),
        }, **self._auth(user))
        self.assertEqual(response.status_code, 201, response.content)

        data = response.json()
        self.assertEqual(data['website'], 'https://buxorotekstil.uz')
        self.assertEqual(data['instagram'], 'buxorotekstil')
        self.assertTrue(data['logo_url'])
        self.assertEqual(data['status'], 'pending')
        # Telefon berilmagan — hisobdagisi olinadi
        self.assertEqual(data['phone'], '+998901112233')

        # Logo bor, lekin rasm hali yo'q — anketa tugamagan
        me = self.client.get('/api/v1/auth/me/', **self._auth(user)).json()
        self.assertEqual(me['onboarding'], 'business')

        self.client.post('/api/v1/me/business/gallery/', {'images': [_png('ish.png')]},
                         **self._auth(user))
        me = self.client.get('/api/v1/auth/me/', **self._auth(user)).json()
        self.assertIsNone(me['onboarding'])

    def test_logo_is_required(self):
        entrepreneur = self._user(is_verified=True, role='entrepreneur')
        response = self.client.post('/api/v1/me/business/', {
            'name': "Buxoro Tekstil", 'sphere': 'ishlab_chiqarish',
            'description': "Paxtadan mato ishlab chiqaramiz va eksport qilamiz.",
        }, **self._auth(entrepreneur))
        self.assertEqual(response.status_code, 400)
        self.assertIn('logo', response.json())

        startupper = self._user(email='s2@mentadbirkor.uz', is_verified=True, role='startupper')
        response = self.client.post('/api/v1/me/startup/', {
            'name': "Tilchi AI", 'sphere': 'it', 'stage': 'mvp',
            'about': "O'zbek tilida nutqni matnga aylantiradigan ochiq model.",
        }, **self._auth(startupper))
        self.assertEqual(response.status_code, 400)
        self.assertIn('logo', response.json())

    def test_edit_keeps_existing_logo(self):
        user = self._user(is_verified=True, role='entrepreneur')
        self.client.post('/api/v1/me/business/', {
            'name': "Buxoro Tekstil", 'sphere': 'ishlab_chiqarish',
            'description': "Paxtadan mato ishlab chiqaramiz va eksport qilamiz.",
            'logo': _png('logo.png'),
        }, **self._auth(user))

        # Tahrirlashda logoni qayta yuborish shart emas
        response = self.client.post('/api/v1/me/business/', {'employees': '50'},
                                    **self._auth(user))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['logo_url'])

    def test_business_needs_real_description(self):
        user = self._user(is_verified=True, role='entrepreneur')
        response = self.client.post('/api/v1/me/business/', {
            'name': "Do'kon", 'sphere': 'savdo', 'description': "Qisqa",
        }, **self._auth(user))
        self.assertEqual(response.status_code, 400)
        self.assertIn('description', response.json())

    def test_bad_stir_is_rejected(self):
        user = self._user(is_verified=True, role='entrepreneur')
        response = self.client.post('/api/v1/me/business/', {
            'name': "Do'kon", 'sphere': 'savdo', 'stir': '12ab',
            'description': "Kiyim-kechak savdosi bilan shug'ullanamiz, uchta filial bor.",
        }, **self._auth(user))
        self.assertEqual(response.status_code, 400)
        self.assertIn('stir', response.json())

    def test_gallery_upload_limit_and_delete(self):
        user = self._user(is_verified=True, role='entrepreneur')
        self.client.post('/api/v1/me/business/', {
            'name': "Buxoro Tekstil", 'sphere': 'ishlab_chiqarish',
            'description': "Paxtadan mato ishlab chiqaramiz va eksport qilamiz.",
            'logo': _png('logo.png'),
        }, **self._auth(user))

        response = self.client.post('/api/v1/me/business/gallery/',
                                    {'images': [_png('a.png'), _png('b.png')]},
                                    **self._auth(user))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(response.json()), 2)

        too_many = self.client.post('/api/v1/me/business/gallery/',
                                    {'images': [_png(f'{i}.png') for i in range(7)]},
                                    **self._auth(user))
        self.assertEqual(too_many.status_code, 400)

        image_id = response.json()[0]['id']
        deleted = self.client.delete(f'/api/v1/me/business/gallery/{image_id}/',
                                     **self._auth(user))
        self.assertEqual(deleted.status_code, 204)

    def test_cannot_delete_someone_elses_photo(self):
        owner = self._user(is_verified=True, role='entrepreneur')
        self.client.post('/api/v1/me/business/', {
            'name': "Buxoro Tekstil", 'sphere': 'ishlab_chiqarish',
            'description': "Paxtadan mato ishlab chiqaramiz va eksport qilamiz.",
            'logo': _png('logo.png'),
        }, **self._auth(owner))
        photo = self.client.post('/api/v1/me/business/gallery/', {'images': [_png()]},
                                 **self._auth(owner)).json()[0]

        stranger = self._user(email='begona@mentadbirkor.uz', is_verified=True)
        response = self.client.delete(f"/api/v1/me/business/gallery/{photo['id']}/",
                                      **self._auth(stranger))
        self.assertEqual(response.status_code, 404)

    def test_gallery_needs_business_first(self):
        user = self._user(is_verified=True, role='entrepreneur')
        response = self.client.post('/api/v1/me/business/gallery/', {'images': [_png()]},
                                    **self._auth(user))
        self.assertEqual(response.status_code, 400)

    def test_startup_completes_onboarding(self):
        user = self._user(is_verified=True, role='startupper', region='samarqand')

        response = self.client.post('/api/v1/me/startup/', {
            'name': "Tilchi AI",
            'sphere': 'it',
            'stage': 'mvp',
            'about': "O'zbek tilida nutqni matnga aylantiradigan ochiq model.",
            'team_size': '4',
            'needed_investment': '150000000',
            'logo': _png('logo.png'),
        }, **self._auth(user))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()['logo_url'])

        startup = Startup.objects.get()
        self.assertEqual(startup.user, user)
        self.assertEqual(startup.region, 'samarqand')

        me = self.client.get('/api/v1/auth/me/', **self._auth(user)).json()
        self.assertIsNone(me['onboarding'])

    def test_rejected_profile_goes_back_to_review_after_edit(self):
        user = self._user(is_verified=True, role='entrepreneur')
        self.client.post('/api/v1/me/business/', {
            'name': "Buxoro Tekstil", 'sphere': 'ishlab_chiqarish',
            'description': "Paxtadan mato ishlab chiqaramiz va eksport qilamiz.",
            'logo': _png('logo.png'),
        }, **self._auth(user))
        BusinessProfile.objects.update(status='rejected')

        response = self.client.post('/api/v1/me/business/', {'employees': '40'},
                                    **self._auth(user))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'pending')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PanelUserManagementTests(TestCase):
    """Panel: foydalanuvchini ko'rish, anketasini tasdiqlash, o'chirish."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='boss@mentadbirkor.uz', password='Parol12345', full_name="Bosh")
        self.user = User.objects.create_user(
            email='tadbirkor2@mentadbirkor.uz', password=None, full_name="Tadbirkor",
            role='entrepreneur', is_verified=True)
        self.business = BusinessProfile.objects.create(
            user=self.user, name="Buxoro Tekstil", sphere='ishlab_chiqarish',
            description="Paxtadan mato ishlab chiqaramiz.")

    def _auth(self, user=None):
        return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user or self.admin)['access']}"}

    def test_detail_shows_business(self):
        data = self.client.get(f'/api/v1/panel/users/{self.user.pk}/', **self._auth()).json()
        self.assertEqual(data['user']['full_name'], "Tadbirkor")
        self.assertEqual(data['business']['name'], "Buxoro Tekstil")
        self.assertEqual(data['startups'], [])

    def test_list_shows_profile_status(self):
        rows = self.client.get('/api/v1/panel/users/', **self._auth()).json()['results']
        row = next(item for item in rows if item['id'] == self.user.pk)
        self.assertEqual(row['profile_status'], 'pending')

    def test_pending_filter(self):
        User.objects.create_user(email='oddiy5@mentadbirkor.uz', password=None, full_name="O")
        data = self.client.get('/api/v1/panel/users/?tekshiruv=1', **self._auth()).json()
        self.assertEqual([row['id'] for row in data['results']], [self.user.pk])
        self.assertEqual(data['pending_profiles'], 1)

    def test_approve_notifies_user(self):
        response = self.client.post(f'/api/v1/panel/users/{self.user.pk}/profil/',
                                    {'status': 'approved'}, content_type='application/json',
                                    **self._auth())
        self.assertEqual(response.status_code, 200)

        self.business.refresh_from_db()
        self.assertEqual(self.business.status, 'approved')
        self.assertEqual(self.user.notifications.count(), 1)

    def test_reject_with_reason(self):
        self.client.post(f'/api/v1/panel/users/{self.user.pk}/profil/',
                         {'status': 'rejected', 'note': "Logotip yo'q"},
                         content_type='application/json', **self._auth())
        note = self.user.notifications.get()
        self.assertIn("Logotip", note.message)

    def test_delete_user_removes_everything(self):
        Startup.objects.create(user=self.user, full_name="T", phone="1", email="t@t.uz",
                               region='samarqand', name="S", sphere='it', about="x" * 40)

        response = self.client.delete(f'/api/v1/panel/users/{self.user.pk}/', **self._auth())
        self.assertEqual(response.status_code, 200)

        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(BusinessProfile.objects.exists())
        # Startap egasiz qolib ketmaydi
        self.assertFalse(Startup.objects.exists())

    def test_cannot_delete_self_or_superuser(self):
        self.assertEqual(
            self.client.delete(f'/api/v1/panel/users/{self.admin.pk}/',
                               **self._auth()).status_code, 400)

        other_admin = User.objects.create_superuser(
            email='boss2@mentadbirkor.uz', password='Parol12345', full_name="Boshqa")
        self.assertEqual(
            self.client.delete(f'/api/v1/panel/users/{other_admin.pk}/',
                               **self._auth()).status_code, 400)

    def test_plain_user_cannot_delete(self):
        victim = User.objects.create_user(email='v@mentadbirkor.uz', password=None,
                                          full_name="V")
        response = self.client.delete(f'/api/v1/panel/users/{victim.pk}/',
                                      **self._auth(self.user))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(User.objects.filter(pk=victim.pk).exists())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PublicDirectoryTests(TestCase):
    """Ochiq ro'yxatlar: faqat tasdiqlangan va yashirilmagan anketalar."""

    def setUp(self):
        owner = User.objects.create_user(email='egasi@mentadbirkor.uz', password=None,
                                         full_name="Dilshod Karimov", role='entrepreneur')
        self.approved = BusinessProfile.objects.create(
            user=owner, name="Buxoro Tekstil", sphere='ishlab_chiqarish', region='buxoro',
            description="Mato ishlab chiqaramiz.", status='approved', phone='+998901112233',
            logo=_png('logo.png'))
        GalleryImage.objects.create(business=self.approved, image=_png('ish.png'))

        other = User.objects.create_user(email='kutuvchi@mentadbirkor.uz', password=None,
                                         full_name="Kutuvchi", role='entrepreneur')
        self.pending = BusinessProfile.objects.create(
            user=other, name="Tekshiruvdagi", sphere='savdo', description="X", status='pending')

        self.startup = Startup.objects.create(
            full_name="Kamola Tosheva", phone="1", email="k@t.uz", region='samarqand',
            name="Tilchi AI", sphere='it', stage='mvp', about="Nutqni matnga aylantiradi.",
            status='approved', logo=_png('s.png'))
        Startup.objects.create(
            full_name="X", phone="1", email="x@t.uz", region='samarqand', name="Yashirin",
            sphere='it', about="Y", status='approved', is_public=False)
        Startup.objects.create(
            full_name="X", phone="1", email="x@t.uz", region='samarqand', name="Kutilmoqda",
            sphere='it', about="Y", status='pending')

    def test_business_list_shows_only_approved(self):
        rows = self.client.get('/api/v1/businesses/').json()['results']
        self.assertEqual([row['name'] for row in rows], ["Buxoro Tekstil"])
        self.assertTrue(rows[0]['logo_url'])
        self.assertTrue(rows[0]['cover_url'])
        self.assertEqual(rows[0]['photo_count'], 1)
        self.assertEqual(rows[0]['sphere_icon'], 'ic-package')

    def test_business_filters(self):
        self.assertEqual(
            self.client.get('/api/v1/businesses/?soha=savdo').json()['count'], 0)
        self.assertEqual(
            self.client.get('/api/v1/businesses/?hudud=buxoro').json()['count'], 1)
        self.assertEqual(
            self.client.get('/api/v1/businesses/?q=tekstil').json()['count'], 1)

    def test_business_detail(self):
        data = self.client.get(f'/api/v1/businesses/{self.approved.pk}/').json()
        self.assertEqual(data['owner_name'], "Dilshod Karimov")
        self.assertEqual(data['phone'], '+998901112233')
        self.assertEqual(len(data['gallery']), 1)

        # Tekshiruvdagi anketa ochiq sahifada yo'q
        self.assertEqual(
            self.client.get(f'/api/v1/businesses/{self.pending.pk}/').status_code, 404)

    def test_startup_list_and_detail(self):
        rows = self.client.get('/api/v1/startups/').json()['results']
        self.assertEqual([row['name'] for row in rows], ["Tilchi AI"])
        self.assertTrue(rows[0]['logo_url'])

        data = self.client.get(f'/api/v1/startups/{self.startup.pk}/').json()
        self.assertEqual(data['full_name'], "Kamola Tosheva")
        self.assertEqual(
            self.client.get('/api/v1/startups/?bosqich=idea').json()['count'], 0)

    def test_overview_includes_directory(self):
        data = self.client.get('/api/v1/overview/').json()
        self.assertEqual(data['stats']['businesses'], 1)
        self.assertEqual(data['stats']['startups'], 1)
        self.assertEqual(len(data['businesses']), 1)
        self.assertEqual(len(data['startups']), 1)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PeerOnboardingTests(TestCase):
    """Yosh: qayerda o'qiydi → chet elda bo'lsa anketa → tengdoshlar ro'yxatida."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='talaba@test.uz', full_name="Malika Rahimova", role='yosh',
            is_verified=True, age=21, phone='+998901112233', region='buxoro')
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(self.user)['access']}"}

    def _form(self, **extra):
        data = {'country': 'korea', 'institution': "Seoul National University", 'course': '2',
                'field': "Kompyuter injiniringi", 'achievements': "Olimpiada g'olibi",
                'phone': '+821012345678', 'telegram': '@malika', 'email': 'malika@gmail.com',
                'photo': _png('men.png')}
        data.update(extra)
        return data

    def test_uzbekistan_finishes_onboarding(self):
        response = self.client.patch('/api/v1/auth/me/', {'study_location': 'uz'},
                                     content_type='application/json', **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['onboarding'])

    def test_abroad_profile_is_published_immediately(self):
        self.client.patch('/api/v1/auth/me/', {'study_location': 'abroad'},
                          content_type='application/json', **self.auth)
        me = self.client.get('/api/v1/auth/me/', **self.auth).json()
        self.assertEqual(me['onboarding'], 'peer')

        response = self.client.post('/api/v1/me/peer/', self._form(), **self.auth)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['telegram'], 'malika')

        me = self.client.get('/api/v1/auth/me/', **self.auth).json()
        self.assertIsNone(me['onboarding'])
        self.assertEqual(me['age'], 21)

        rows = self.client.get('/api/v1/peers/').json()['results']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['full_name'], "Malika Rahimova")
        self.assertEqual(rows[0]['course'], 2)
        self.assertEqual(rows[0]['age'], 21)
        self.assertEqual(rows[0]['home_region'], 'buxoro')

    def test_photo_required_and_achievements_limited(self):
        form = self._form(achievements='x' * 301)
        del form['photo']
        response = self.client.post('/api/v1/me/peer/', form, **self.auth)
        self.assertEqual(response.status_code, 400)
        self.assertIn('achievements', response.json())

        response = self.client.post('/api/v1/me/peer/', self._form(photo=''), **self.auth)
        self.assertEqual(response.status_code, 400)
        self.assertIn('photo', response.json())

    def test_edit_keeps_photo(self):
        self.client.post('/api/v1/me/peer/', self._form(), **self.auth)
        form = self._form(course='3')
        del form['photo']
        response = self.client.post('/api/v1/me/peer/', form, **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['course'], 3)

    def test_overview_counts_youth_only(self):
        User.objects.create_user(email='katta@test.uz', full_name="Katta", role='yosh', age=45)
        User.objects.create_user(email='org@test.uz', full_name="Tashkilot", role='organization')
        data = self.client.get('/api/v1/overview/').json()
        self.assertEqual(data['stats']['users'], 1)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MediaUrlTests(TestCase):
    """Rasm havolasi brauzerda ochiladigan bo'lsin (ichki `web:8000` emas)."""

    def setUp(self):
        from apps.abroad.models import Peer
        user = User.objects.create_user(email='rasm@test.uz', full_name="Rasm Test", role='yosh')
        self.peer = Peer(user=user, full_name="Rasm Test", country='korea', status='approved',
                         is_published=True)
        self.peer.photo.save('men.png', _png(), save=True)

    def _photo(self, **headers):
        return self.client.get(f'/api/v1/peers/{self.peer.pk}/', **headers).json()['photo']

    @override_settings(SITE_URL='https://mentadbirkor.uz', ALLOWED_HOSTS=['*'])
    def test_site_url_is_used_for_internal_requests(self):
        photo = self._photo(HTTP_HOST='web:8000')
        self.assertTrue(photo.startswith('https://mentadbirkor.uz/media/peers/'), photo)

    @override_settings(SITE_URL='', ALLOWED_HOSTS=['*'])
    def test_internal_host_without_site_url_gives_relative(self):
        self.assertTrue(self._photo(HTTP_HOST='web:8000').startswith('/media/peers/'))

    @override_settings(SITE_URL='')
    def test_local_development_keeps_absolute(self):
        self.assertTrue(self._photo().startswith('http://testserver/media/'))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MultiRoleTests(TestCase):
    """Bir odam yosh ham, startupper ham, tadbirkor ham bo'la oladi."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='kop@test.uz', full_name="Ko'p Rolli", role='yosh', is_verified=True,
            study_location='uz', phone='+998901112233', age=22)
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(self.user)['access']}"}

    def _startup(self, name, **extra):
        from apps.startups.models import StartupSphere, StartupStage
        data = {'name': name, 'sphere': StartupSphere.values[0], 'stage': StartupStage.values[0],
                'about': "Bu startap yoshlarga kasb tanlashda yordam beradigan platforma.",
                'team_size': '2', 'logo': _png('logo.png')}
        data.update(extra)
        return self.client.post('/api/v1/me/startups/', data, **self.auth)

    def test_youth_can_add_up_to_three_startups(self):
        for index in range(3):
            response = self._startup(f"Startap {index}")
            self.assertEqual(response.status_code, 201, response.content)

        self.assertEqual(self._startup("To'rtinchi").status_code, 400)

        data = self.client.get('/api/v1/me/startups/', **self.auth).json()
        self.assertEqual(data['limit'], 3)
        self.assertEqual(len(data['results']), 3)

        me = self.client.get('/api/v1/auth/me/', **self.auth).json()
        self.assertEqual(me['capabilities']['startups'], 3)
        # Asosiy roli yosh bo'lib qoladi, ro'yxatdan o'tish tugagan
        self.assertEqual(me['role'], 'yosh')
        self.assertIsNone(me['onboarding'])

    def test_edit_and_delete_own_startup_only(self):
        startup_id = self._startup("Birinchi").json()['id']

        response = self.client.post(f'/api/v1/me/startups/{startup_id}/',
                                    {'name': "Yangi nom"}, **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['name'], "Yangi nom")

        stranger = User.objects.create_user(email='begona@test.uz', full_name="Begona")
        other = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(stranger)['access']}"}
        self.assertEqual(
            self.client.delete(f'/api/v1/me/startups/{startup_id}/', **other).status_code, 404)

        self.assertEqual(
            self.client.delete(f'/api/v1/me/startups/{startup_id}/', **self.auth).status_code, 204)
        self.assertEqual(self.user.startups.count(), 0)

    def test_choosing_uzbekistan_hides_peer_profile(self):
        from apps.abroad.models import Peer
        form = {'country': 'korea', 'institution': "SNU", 'course': '2', 'field': "IT",
                'phone': '+821012345678', 'photo': _png('men.png')}
        self.client.post('/api/v1/me/peer/', form, **self.auth)
        self.assertEqual(self.client.get('/api/v1/peers/').json()['count'], 1)

        self.client.patch('/api/v1/auth/me/', {'study_location': 'uz'},
                          content_type='application/json', **self.auth)
        self.assertEqual(self.client.get('/api/v1/peers/').json()['count'], 0)

        # Chet elga qaytsa — yana ko'rinadi
        self.client.post('/api/v1/me/peer/', {'course': '3'}, **self.auth)
        self.assertEqual(self.client.get('/api/v1/peers/').json()['count'], 1)
        self.assertTrue(Peer.objects.get().is_published)

    def test_session_lasts_24_hours(self):
        from datetime import timedelta
        self.assertEqual(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'], timedelta(hours=24))
        self.assertEqual(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'], timedelta(hours=24))
        self.assertFalse(settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS'])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SiteCleanupTests(TestCase):
    """`saytni_tozalash`: `--ha` siz hech narsa o'chmaydi."""

    def setUp(self):
        from apps.abroad.models import Peer
        from apps.cabinet.models import Notification

        self.admin = User.objects.create_superuser(email='bosh@test.uz', password='x', full_name="Bosh")
        self.youth = User.objects.create_user(email='yosh@test.uz', full_name="Yosh", role='yosh')
        peer = Peer(user=self.youth, full_name="Yosh", country='korea')
        peer.photo.save('men.png', _png(), save=True)
        Notification.objects.create(user=self.youth, title="Salom", message="Sinov")

    def test_dry_run_changes_nothing(self):
        from io import StringIO

        from django.core.management import call_command

        from apps.abroad.models import Peer
        out = StringIO()
        call_command('saytni_tozalash', stdout=out)
        self.assertIn("Hech narsa o'chirilmadi", out.getvalue())
        self.assertEqual(Peer.objects.count(), 1)

    def test_delete_content_and_optionally_users(self):
        from io import StringIO

        from django.core.management import call_command

        from apps.abroad.models import Peer
        from apps.cabinet.models import Notification
        call_command('saytni_tozalash', '--ha', stdout=StringIO())
        self.assertEqual(Peer.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertTrue(User.objects.filter(pk=self.youth.pk).exists())

        call_command('saytni_tozalash', '--ha', '--userlar', stdout=StringIO())
        self.assertFalse(User.objects.filter(pk=self.youth.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())


class PanelDeleteAllTests(TestCase):
    """Panelning «Hammasini o'chirish» tugmasi."""

    def setUp(self):
        self.admin = User.objects.create_superuser(email='panel@test.uz', password='x', full_name="Panel")
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(self.admin)['access']}"}
        for index in range(3):
            Initiative.objects.create(direction='eco', kind='idea', title=f"G'oya {index}",
                                      description="X", author_name="A", vote_count=5)

    def test_admin_deletes_every_initiative(self):
        response = self.client.delete('/api/v1/panel/initiatives/hammasi/', **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['deleted'], 3)
        self.assertFalse(Initiative.objects.exists())

    def test_regular_user_cannot(self):
        user = User.objects.create_user(email='oddiy@test.uz', full_name="Oddiy")
        auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}
        response = self.client.delete('/api/v1/panel/initiatives/hammasi/', **auth)
        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(Initiative.objects.count(), 3)

    def test_unknown_resource(self):
        response = self.client.delete('/api/v1/panel/users/hammasi/', **self.auth)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
