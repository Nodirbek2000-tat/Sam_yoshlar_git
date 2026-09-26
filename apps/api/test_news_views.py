"""Yangilik ko'rishlari: sahifa keshlanadi, o'qilgani alohida yuboriladi."""

from django.test import TestCase, override_settings

from apps.content.models import News

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'news-views-tests'}}


@override_settings(CACHES=LOCMEM)
class NewsViewTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.news = News.objects.create(title="Ko'rish sinovi", excerpt="Qisqa", body="Matn",
                                        category='grant', is_published=True)

    def test_reading_detail_does_not_count(self):
        self.client.get(f'/api/v1/news/{self.news.slug}/')
        self.client.get(f'/api/v1/news/{self.news.slug}/')
        self.news.refresh_from_db()
        self.assertEqual(self.news.views, 0)

    def test_view_is_counted_once_per_visitor(self):
        url = f'/api/v1/news/{self.news.slug}/korildi/'
        first = self.client.post(url, HTTP_X_FORWARDED_FOR='203.0.113.5')
        again = self.client.post(url, HTTP_X_FORWARDED_FOR='203.0.113.5')
        other = self.client.post(url, HTTP_X_FORWARDED_FOR='198.51.100.7')

        self.assertEqual(first.json()['views'], 1)
        self.assertEqual(again.json()['views'], 1)       # sahifani yangilash sanalmaydi
        self.assertEqual(other.json()['views'], 2)

    def test_unknown_or_hidden_news(self):
        self.assertEqual(self.client.post('/api/v1/news/yoq/korildi/').status_code, 404)
        News.objects.filter(pk=self.news.pk).update(is_published=False)
        self.assertEqual(
            self.client.post(f'/api/v1/news/{self.news.slug}/korildi/').status_code, 404)
