from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cabinet.models import Appeal
from apps.content.models import Announcement, Event, EventRegistration, News
from apps.core.constants import Status

User = get_user_model()


#: Panelning barcha kirish nuqtalari — hech biri begonaga ochiq bo'lmasligi kerak.
PANEL_URLS = [
    ('panel:dashboard', {}),
    ('panel:news', {}),
    ('panel:news_create', {}),
    ('panel:events', {}),
    ('panel:event_create', {}),
    ('panel:announcements', {}),
    ('panel:announcement_create', {}),
    ('panel:users', {}),
    ('panel:appeals', {}),
    ('panel:suggestions', {}),
    ('panel:startups', {}),
    ('panel:problems', {}),
    ('panel:solutions', {}),
    ('panel:settings', {}),
    ('panel:voice', {}),
    ('panel:initiatives', {}),
]


class PanelAccessTests(TestCase):
    """Panelga faqat tasdiqlangan admin kira oladi; boshqalar uchun 404."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@samyosh.uz', password='Samyosh2026!', full_name="Bosh Admin",
        )
        self.regular = User.objects.create_user(
            email='oddiy@example.com', password='Samyosh2026!', full_name="Oddiy Foydalanuvchi",
        )

    def test_anonymous_gets_404(self):
        """Kirmagan odam havolani tersa ham hech narsa ko'rmaydi — 404, login sahifasi emas."""
        for name, kwargs in PANEL_URLS:
            with self.subTest(url=name):
                response = self.client.get(reverse(name, kwargs=kwargs))
                self.assertEqual(response.status_code, 404)

    def test_regular_user_gets_404(self):
        self.client.force_login(self.regular)
        for name, kwargs in PANEL_URLS:
            with self.subTest(url=name):
                response = self.client.get(reverse(name, kwargs=kwargs))
                self.assertEqual(response.status_code, 404)

    def test_staff_without_verification_gets_404(self):
        """Xodim bo'lsa ham, tasdiqlanmagan bo'lsa kira olmaydi."""
        staff = User.objects.create_user(
            email='xodim@samyosh.uz', password='Samyosh2026!', full_name="Xodim",
            is_staff=True, role='admin', is_verified=False,
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 404)

    def test_verified_admin_role_can_enter(self):
        staff = User.objects.create_user(
            email='moder@samyosh.uz', password='Samyosh2026!', full_name="Moderator",
            is_staff=True, role='admin', is_verified=True,
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 200)

    def test_blocked_admin_cannot_enter(self):
        self.admin.is_active = False
        self.admin.save()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 404)

    def test_superuser_sees_everything(self):
        self.client.force_login(self.admin)
        for name, kwargs in PANEL_URLS:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name, kwargs=kwargs)).status_code, 200)

    def test_no_data_leaks_to_outsider(self):
        """Begona foydalanuvchi javobida hech qanday maxfiy ma'lumot bo'lmasligi kerak."""
        News.objects.create(title="Maxfiy qoralama", category='grant', excerpt="X", body="Y",
                            is_published=False)
        Appeal.objects.create(user=self.regular, subject="Shaxsiy murojaat", message="Matn")

        other = User.objects.create_user(email='begona@example.com', password='Samyosh2026!',
                                         full_name="Begona")
        self.client.force_login(other)

        for name in ['panel:news', 'panel:appeals', 'panel:users']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 404)
            body = response.content.decode()
            self.assertNotIn("Maxfiy qoralama", body)
            self.assertNotIn("Shaxsiy murojaat", body)
            self.assertNotIn("oddiy@example.com", body)

    def test_post_endpoints_also_blocked(self):
        """O'chirish/o'zgartirish so'rovlari ham 404 — POST orqali ham kirib bo'lmaydi."""
        news = News.objects.create(title="Yangilik", category='grant', excerpt="X", body="Y")
        self.client.force_login(self.regular)

        response = self.client.post(reverse('panel:news_delete', kwargs={'pk': news.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(News.objects.filter(pk=news.pk).exists())


class PanelContentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@samyosh.uz', password='Samyosh2026!', full_name="Bosh Admin",
        )
        self.client.force_login(self.admin)

    def test_create_news(self):
        response = self.client.post(reverse('panel:news_create'), {
            'title': "Panel orqali qo'shilgan yangilik",
            'category': 'grant',
            'excerpt': "Qisqacha matn",
            'body': "To'liq matn",
            'author_name': "Admin",
            'published_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'is_published': 'on',
        })
        self.assertRedirects(response, reverse('panel:news'))
        news = News.objects.get(title="Panel orqali qo'shilgan yangilik")
        self.assertTrue(news.is_published)
        self.assertEqual(news.author, self.admin)

        # Saytda ko'rinishi kerak
        self.client.logout()
        public = self.client.get(reverse('content:news_list'))
        self.assertContains(public, "Panel orqali qo")

    def test_create_event(self):
        starts = timezone.now() + timedelta(days=7)
        response = self.client.post(reverse('panel:event_create'), {
            'title': "Panel tadbiri",
            'description': "Tavsif",
            'starts_at': starts.strftime('%Y-%m-%dT%H:%M'),
            'location': "Toshkent, IT Park",
            'capacity': 50,
            'is_published': 'on',
        })
        self.assertRedirects(response, reverse('panel:events'))
        self.assertTrue(Event.objects.filter(title="Panel tadbiri").exists())

    def test_event_end_before_start_rejected(self):
        starts = timezone.now() + timedelta(days=7)
        response = self.client.post(reverse('panel:event_create'), {
            'title': "Xato tadbir", 'description': "X",
            'starts_at': starts.strftime('%Y-%m-%dT%H:%M'),
            'ends_at': (starts - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'location': "Toshkent", 'capacity': 10, 'is_published': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Event.objects.filter(title="Xato tadbir").exists())

    def test_create_announcement(self):
        response = self.client.post(reverse('panel:announcement_create'), {
            'title': "Panel e'loni", 'type': 'grant', 'body': "Matn",
            'posted_at': timezone.localdate().strftime('%Y-%m-%d'),
            'deadline': (timezone.localdate() + timedelta(days=20)).strftime('%Y-%m-%d'),
            'is_active': 'on',
        })
        self.assertRedirects(response, reverse('panel:announcements'))
        self.assertTrue(Announcement.objects.filter(title="Panel e'loni").exists())

    def test_verify_user_creates_notification(self):
        person = User.objects.create_user(email='yangi@example.com', password='Samyosh2026!',
                                          full_name="Yangi User")
        self.client.post(reverse('panel:user_toggle', kwargs={'pk': person.pk, 'action': 'verify'}))

        person.refresh_from_db()
        self.assertTrue(person.is_verified)
        self.assertEqual(person.notifications.count(), 1)

    def test_cannot_change_own_account(self):
        response = self.client.post(
            reverse('panel:user_toggle', kwargs={'pk': self.admin.pk, 'action': 'block'})
        )
        self.assertRedirects(response, reverse('panel:user_detail', kwargs={'pk': self.admin.pk}))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_appeal_response_notifies_user(self):
        person = User.objects.create_user(email='murojaat@example.com', password='Samyosh2026!',
                                          full_name="Murojaatchi")
        appeal = Appeal.objects.create(user=person, subject="Savol", message="Matn")

        self.client.post(reverse('panel:appeal_detail', kwargs={'pk': appeal.pk}), {
            'status': Status.DONE, 'response': "Javobimiz shu.",
        })

        appeal.refresh_from_db()
        self.assertEqual(appeal.status, Status.DONE)
        self.assertEqual(appeal.responded_by, self.admin)
        self.assertIsNotNone(appeal.responded_at)
        self.assertEqual(person.notifications.count(), 1)


class PanelVoiceTests(TestCase):
    """Panelda tashabbuslar va reyting ko'rinishi."""

    def setUp(self):
        from apps.initiatives.models import Initiative

        self.admin = User.objects.create_superuser(
            email='admin@samyosh.uz', password='Samyosh2026!', full_name="Bosh Admin",
        )
        self.client.force_login(self.admin)
        self.idea = Initiative.objects.create(
            direction='eco', kind='idea', title="Plastik yig'ish punktlari",
            description="Maktablarda yig'ish punkti.", author_name="Aziz Rahimov",
            vote_count=12,
        )

    def test_overview_shows_top_ideas(self):
        response = self.client.get(reverse('panel:voice'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plastik yig")
        self.assertContains(response, "Ekologiya")

    def test_list_filters_by_direction(self):
        from apps.initiatives.models import Initiative
        Initiative.objects.create(direction='ai', kind='idea', title="Neyron baza",
                                  description="X", author_name="Bobur")

        response = self.client.get(reverse('panel:initiatives'), {'yonalish': 'eco'})
        self.assertContains(response, "Plastik yig")
        self.assertNotContains(response, "Neyron baza")

    def test_detail_shows_rank_and_moderation(self):
        response = self.client.get(reverse('panel:initiative_detail', kwargs={'pk': self.idea.pk}))
        self.assertContains(response, "Moderatsiya")
        self.assertEqual(response.context['rank'], 1)

    def test_moderation_notifies_author(self):
        person = User.objects.create_user(email='muallif@example.com', password='Samyosh2026!',
                                          full_name="Muallif")
        self.idea.author = person
        self.idea.save()

        response = self.client.post(reverse('panel:initiative_detail', kwargs={'pk': self.idea.pk}),
                                    {'status': 'rejected', 'admin_note': "Aniqroq yozing",
                                     'is_published': 'on'})
        self.assertRedirects(response, reverse('panel:initiatives'))

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.status, 'rejected')
        self.assertEqual(self.idea.admin_note, "Aniqroq yozing")
        self.assertEqual(person.notifications.count(), 1)

    def test_outsider_cannot_see_initiatives(self):
        outsider = User.objects.create_user(email='begona@example.com', password='Samyosh2026!',
                                            full_name="Begona")
        self.client.force_login(outsider)

        for name in ['panel:voice', 'panel:initiatives']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("Plastik yig", response.content.decode())


class PanelAdminGrantTests(TestCase):
    """Bitta tugma bilan adminlik berish."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='bosh@samyosh.uz', password='Samyosh2026!', full_name="Bosh Admin",
        )
        self.person = User.objects.create_user(
            email='oddiy@example.com', password='Samyosh2026!', full_name="Oddiy User",
        )
        self.client.force_login(self.admin)

    def test_grant_admin(self):
        url = reverse('panel:user_toggle', kwargs={'pk': self.person.pk, 'action': 'admin'})
        self.client.post(url)

        self.person.refresh_from_db()
        self.assertTrue(self.person.is_staff)
        self.assertTrue(self.person.is_verified)
        self.assertEqual(self.person.role, 'admin')
        self.assertEqual(self.person.notifications.count(), 1)

    def test_new_admin_can_enter_panel(self):
        self.client.post(reverse('panel:user_toggle',
                                 kwargs={'pk': self.person.pk, 'action': 'admin'}))

        self.client.force_login(self.person)
        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 200)

    def test_revoke_admin(self):
        url = reverse('panel:user_toggle', kwargs={'pk': self.person.pk, 'action': 'admin'})
        self.client.post(url)          # berdik
        self.client.post(url)          # olib qo'ydik

        self.person.refresh_from_db()
        self.assertFalse(self.person.is_staff)

        self.client.force_login(self.person)
        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 404)

    def test_cannot_change_own_rights(self):
        self.client.post(reverse('panel:user_toggle',
                                 kwargs={'pk': self.admin.pk, 'action': 'admin'}))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff)


class PanelVoteToolsTests(TestCase):
    """Tashabbus ovozini qo'lda sozlash."""

    def setUp(self):
        from apps.initiatives.models import Initiative

        self.admin = User.objects.create_superuser(
            email='admin@samyosh.uz', password='Samyosh2026!', full_name="Admin",
        )
        self.idea = Initiative.objects.create(
            direction='eco', kind='idea', title="G'oya", description="X",
            author_name="A", vote_count=10,
        )
        self.client.force_login(self.admin)
        self.url = reverse('panel:initiative_votes', kwargs={'pk': self.idea.pk})

    def test_add_votes(self):
        self.client.post(self.url, {'delta': '50'})
        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 60)

    def test_subtract_votes(self):
        self.client.post(self.url, {'delta': '-10'})
        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 0)

    def test_never_below_zero(self):
        self.client.post(self.url, {'delta': '-999'})
        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 0)

    def test_set_exact(self):
        self.client.post(self.url, {'exact': '777'})
        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 777)

    def test_real_votes_still_work_after_manual_change(self):
        """Qo'lda qo'yilgan ovoz haqiqiy ovozni buzmaydi."""
        self.client.post(self.url, {'exact': '100'})
        self.client.logout()

        vote_url = reverse('initiatives:vote', kwargs={'pk': self.idea.pk})
        data = self.client.post(vote_url).json()

        self.assertTrue(data['ok'])
        self.assertEqual(data['votes'], 101)

    def test_outsider_cannot_change_votes(self):
        outsider = User.objects.create_user(email='begona@example.com',
                                            password='Samyosh2026!', full_name="Begona")
        self.client.force_login(outsider)
        response = self.client.post(self.url, {'exact': '9999'})

        self.assertEqual(response.status_code, 404)
        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 10)


class PanelDeleteTests(TestCase):
    """Ro'yxatlardan to'g'ridan-to'g'ri o'chirish."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@samyosh.uz', password='Samyosh2026!', full_name="Admin",
        )
        self.client.force_login(self.admin)

        self.news = News.objects.create(title="O'chiriladigan yangilik", category='grant',
                                        excerpt="X", body="Y")
        self.event = Event.objects.create(title="O'chiriladigan tadbir", description="X",
                                          starts_at=timezone.now() + timedelta(days=5),
                                          location="Toshkent", capacity=10)
        self.announcement = Announcement.objects.create(title="O'chiriladigan e'lon",
                                                        type='grant', body="X")

    def test_delete_buttons_shown_in_lists(self):
        pairs = [
            ('panel:news', 'panel:news_delete', self.news.pk),
            ('panel:events', 'panel:event_delete', self.event.pk),
            ('panel:announcements', 'panel:announcement_delete', self.announcement.pk),
        ]
        for list_name, delete_name, pk in pairs:
            with self.subTest(page=list_name):
                response = self.client.get(reverse(list_name))
                self.assertContains(response, reverse(delete_name, kwargs={'pk': pk}))

    def test_delete_news(self):
        response = self.client.post(reverse('panel:news_delete', kwargs={'pk': self.news.pk}))
        self.assertRedirects(response, reverse('panel:news'))
        self.assertFalse(News.objects.filter(pk=self.news.pk).exists())

    def test_delete_event_removes_registrations(self):
        person = User.objects.create_user(email='k@example.com', password='Samyosh2026!',
                                          full_name="Kishi")
        EventRegistration.objects.create(event=self.event, user=person)

        self.client.post(reverse('panel:event_delete', kwargs={'pk': self.event.pk}))

        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())
        self.assertEqual(EventRegistration.objects.count(), 0)

    def test_delete_announcement(self):
        self.client.post(reverse('panel:announcement_delete',
                                 kwargs={'pk': self.announcement.pk}))
        self.assertFalse(Announcement.objects.filter(pk=self.announcement.pk).exists())

    def test_delete_needs_post(self):
        """GET bilan o'chirib bo'lmaydi — tasodifan bosilsa ham xavfsiz."""
        response = self.client.get(reverse('panel:news_delete', kwargs={'pk': self.news.pk}))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(News.objects.filter(pk=self.news.pk).exists())

    def test_outsider_cannot_delete(self):
        outsider = User.objects.create_user(email='begona@example.com',
                                            password='Samyosh2026!', full_name="Begona")
        self.client.force_login(outsider)

        for name, pk in [('panel:news_delete', self.news.pk),
                         ('panel:event_delete', self.event.pk),
                         ('panel:announcement_delete', self.announcement.pk)]:
            with self.subTest(url=name):
                response = self.client.post(reverse(name, kwargs={'pk': pk}))
                self.assertEqual(response.status_code, 404)

        self.assertTrue(News.objects.filter(pk=self.news.pk).exists())
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())
        self.assertTrue(Announcement.objects.filter(pk=self.announcement.pk).exists())
