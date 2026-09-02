from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Announcement, AnnouncementType, Event, News, NewsCategory

User = get_user_model()


class NewsTests(TestCase):
    def setUp(self):
        self.news = News.objects.create(
            title="Grant dasturi", category=NewsCategory.GRANT,
            excerpt="Qisqacha", body="Matn",
        )
        News.objects.create(title="Forum bo'ldi", category=NewsCategory.FORUM,
                            excerpt="Qisqacha", body="Matn")

    def test_list_and_filter(self):
        response = self.client.get(reverse('content:news_list'))
        self.assertContains(response, "Grant dasturi")
        self.assertContains(response, "Forum bo")

        filtered = self.client.get(reverse('content:news_list'), {'kategoriya': 'grant'})
        self.assertContains(filtered, "Grant dasturi")
        self.assertNotContains(filtered, "Forum bo")

    def test_search(self):
        response = self.client.get(reverse('content:news_list'), {'q': 'Forum'})
        self.assertNotContains(response, "Grant dasturi")

    def test_detail_increments_views(self):
        self.client.get(self.news.get_absolute_url())
        self.news.refresh_from_db()
        self.assertEqual(self.news.views, 1)


class EventRegistrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='a@b.uz', password='Samyosh2026!',
                                             full_name="Test")
        self.event = Event.objects.create(
            title="Hackathon", description="Tavsif",
            starts_at=timezone.now() + timedelta(days=10),
            location="IT Park", capacity=2,
        )

    def test_register_and_cancel(self):
        self.client.force_login(self.user)
        url = reverse('content:event_register', kwargs={'slug': self.event.slug})

        self.client.post(url)
        self.assertEqual(self.event.registered_count, 1)
        self.assertTrue(self.event.is_registered(self.user))

        self.client.post(url)
        self.assertEqual(self.event.registered_count, 0)

    def test_capacity_limit(self):
        other = User.objects.create_user(email='c@d.uz', password='Samyosh2026!', full_name="B")
        third = User.objects.create_user(email='e@f.uz', password='Samyosh2026!', full_name="C")
        url = reverse('content:event_register', kwargs={'slug': self.event.slug})

        for user in (self.user, other, third):
            self.client.force_login(user)
            self.client.post(url)

        self.assertEqual(self.event.registered_count, 2)
        self.assertTrue(self.event.is_full)

    def test_anonymous_redirected(self):
        url = reverse('content:event_register', kwargs={'slug': self.event.slug})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_past_event_not_registrable(self):
        past = Event.objects.create(title="O'tgan", description="X",
                                    starts_at=timezone.now() - timedelta(days=1),
                                    location="Toshkent", capacity=10)
        self.client.force_login(self.user)
        self.client.post(reverse('content:event_register', kwargs={'slug': past.slug}))
        self.assertEqual(past.registered_count, 0)


class AnnouncementTests(TestCase):
    def test_expired_status(self):
        expired = Announcement.objects.create(
            title="Eski grant", type=AnnouncementType.GRANT, body="Matn",
            deadline=timezone.localdate() - timedelta(days=1),
        )
        self.assertTrue(expired.is_expired)
        self.assertEqual(expired.status_label, "Muddati tugagan")

    def test_filter_by_type(self):
        Announcement.objects.create(title="Grant e'loni", type=AnnouncementType.GRANT, body="M")
        Announcement.objects.create(title="Kredit e'loni", type=AnnouncementType.CREDIT, body="M")

        response = self.client.get(reverse('content:announcement_list'), {'turi': 'grant'})
        self.assertContains(response, "Grant e")
        self.assertNotContains(response, "Kredit e")
