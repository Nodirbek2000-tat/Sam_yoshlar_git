from django.test import TestCase
from django.urls import reverse

from apps.core.constants import Status

from .models import Startup


class StartupRegistrationTests(TestCase):
    def _data(self, **overrides):
        data = {
            'full_name': "Aziza Karimova",
            'phone': '+998901234567',
            'email': 'aziza@example.com',
            'region': 'samarqand',
            'district': "Urgut",
            'name': "SmartQueue",
            'sphere': 'medtech',
            'stage': 'mvp',
            'about': "Klinikalar uchun onlayn navbat tizimi.",
            'team_size': 3,
        }
        data.update(overrides)
        return data

    def test_form_renders(self):
        response = self.client.get(reverse('startups:register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "StartUp ro")

    def test_submission(self):
        response = self.client.post(reverse('startups:register'), self._data())
        self.assertRedirects(response, reverse('startups:success'))

        startup = Startup.objects.get(name="SmartQueue")
        self.assertEqual(startup.status, Status.PENDING)
        self.assertEqual(startup.sphere_icon, 'ic-stethoscope')

    def test_required_fields(self):
        response = self.client.post(reverse('startups:register'), self._data(name=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Startup.objects.count(), 0)

    def test_only_approved_startups_listed(self):
        Startup.objects.create(**self._data(), status=Status.PENDING)
        response = self.client.get(reverse('startups:list'))
        self.assertNotContains(response, "SmartQueue")

        Startup.objects.update(status=Status.APPROVED)
        response = self.client.get(reverse('startups:list'))
        self.assertContains(response, "SmartQueue")
