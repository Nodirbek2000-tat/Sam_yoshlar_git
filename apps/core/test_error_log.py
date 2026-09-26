"""Server xatolari: bazaga yoziladi, birlashadi, botga yuboriladi, panelda boshqariladi."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils import timezone

from .models import ServerError

User = get_user_model()
SECRET = 'xato-test-kalit'


def broken_view(request):
    raise ValueError("Sinov xatosi")


def other_broken_view(request):
    return {}['yoq']                                   # KeyError — boshqa xato


def ok_view(request):
    return HttpResponse("ok")


urlpatterns = [
    path('buzuq/', broken_view),
    path('boshqa-buzuq/', other_broken_view),
    path('yaxshi/', ok_view),
    path('', include('config.urls')),
]


@override_settings(ROOT_URLCONF=__name__, TELEGRAM_API_SECRET=SECRET)
class ErrorLogTests(TestCase):
    def setUp(self):
        self.client.raise_request_exception = False

    def test_500_is_recorded_with_traceback(self):
        response = self.client.get('/buzuq/?sahifa=2')
        self.assertEqual(response.status_code, 500)

        error = ServerError.objects.get()
        self.assertEqual(error.title, "ValueError: Sinov xatosi")
        self.assertEqual(error.method, 'GET')
        self.assertEqual(error.path, '/buzuq/?sahifa=2')
        self.assertIn('apps/core/test_error_log.py', error.location)
        self.assertIn('Traceback', error.traceback)
        self.assertEqual(error.count, 1)

    def test_same_error_is_merged(self):
        for _ in range(3):
            self.client.get('/buzuq/')
        self.client.get('/boshqa-buzuq/')

        self.assertEqual(ServerError.objects.count(), 2)
        self.assertEqual(ServerError.objects.get(title__startswith='ValueError').count, 3)

    def test_normal_requests_and_404_are_not_recorded(self):
        self.client.get('/yaxshi/')
        self.client.get('/api/v1/news/bunday-yangilik-yoq/')
        self.assertFalse(ServerError.objects.exists())

    def test_bot_gets_each_error_once_then_reminder(self):
        self.client.get('/buzuq/')
        url, secret = '/api/telegram/xatolar/', {'HTTP_X_BOT_SECRET': SECRET}

        first = self.client.get(url, **secret).json()
        self.assertEqual([row['title'] for row in first['results']], ["ValueError: Sinov xatosi"])
        self.assertTrue(first['panel'].endswith('/nazorat/xatolar'))
        self.assertEqual(self.client.get(url, **secret).json()['results'], [])

        # Yana chiqdi, lekin hali 6 soat o'tmagan — qayta yuborilmaydi
        self.client.get('/buzuq/')
        self.assertEqual(self.client.get(url, **secret).json()['results'], [])

        # 6 soatdan keyin yana takrorlansa — eslatiladi
        ServerError.objects.update(notified_at=timezone.now() - timedelta(hours=7))
        self.client.get('/buzuq/')
        again = self.client.get(url, **secret).json()['results']
        self.assertEqual(len(again), 1)
        self.assertTrue(again[0]['repeat'])
        self.assertEqual(again[0]['count'], 3)

    def test_bot_endpoint_needs_secret(self):
        self.assertEqual(self.client.get('/api/telegram/xatolar/').status_code, 403)

    def test_panel_lists_and_resolves(self):
        from apps.api.auth_views import tokens_for

        self.client.get('/buzuq/')
        admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")
        auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(admin)['access']}"}

        data = self.client.get('/api/v1/panel/xatolar/', **auth).json()
        self.assertEqual((data['count'], data['last_day']), (1, 1))
        error_id = data['results'][0]['id']

        overview = self.client.get('/api/v1/panel/overview/', **auth).json()
        pending = {row['key']: row['value'] for row in overview['pending']}
        self.assertEqual(pending['errors'], 1)

        self.assertEqual(
            self.client.delete(f'/api/v1/panel/xatolar/{error_id}/', **auth).status_code, 200)
        self.assertFalse(ServerError.objects.exists())

    def test_regular_user_cannot_see_errors(self):
        from apps.api.auth_views import tokens_for

        user = User.objects.create_user(email='y@test.uz', full_name="Y")
        auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}
        self.assertEqual(self.client.get('/api/v1/panel/xatolar/', **auth).status_code, 404)
