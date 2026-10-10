"""Startapchining ijtimoiy holati: bir marta so'raladi, profilda va panelda ko'rinadi."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.startups.models import StartupSphere, StartupStage

from .auth_views import tokens_for
from .tests import _png

User = get_user_model()
MEDIA = tempfile.mkdtemp(prefix='holat-test-')


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


@override_settings(MEDIA_ROOT=MEDIA)
class SocialStatusTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(email='s@test.uz', full_name="Ali Valiyev",
                                             role='startupper', is_verified=True)
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")

    def add(self, user=None, **extra):
        data = {'name': "Tilchi AI", 'sphere': StartupSphere.values[0],
                'stage': StartupStage.values[0], 'team_size': '2', 'logo': _png('logo.png'),
                'about': "O'zbek tilida nutqni matnga aylantiradigan ochiq model.", **extra}
        return self.client.post('/api/v1/me/startups/', data, **auth(user or self.user))

    def test_new_startup_asks_status_once(self):
        response = self.add()
        self.assertEqual(response.status_code, 400)
        self.assertIn('social_status', response.json())

        response = self.add(social_status='student')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Universitet', response.json()['education_place'][0])

        response = self.add(social_status='school')
        self.assertIn('Maktab', response.json()['education_place'][0])

        response = self.add(social_status='student', education_place="  SamDU  ")
        self.assertEqual(response.status_code, 201, response.content)
        self.user.refresh_from_db()
        self.assertEqual((self.user.social_status, self.user.education_place), ('student', 'SamDU'))

        # Ikkinchi startapda qayta so'ralmaydi
        self.assertEqual(self.add(name="Ikkinchi").status_code, 201)

    def test_registration_step_asks_too(self):
        data = {'name': "Tilchi AI", 'sphere': StartupSphere.values[0],
                'stage': StartupStage.values[0], 'logo': _png('logo.png'),
                'about': "O'zbek tilida nutqni matnga aylantiradigan ochiq model."}
        response = self.client.post('/api/v1/me/startup/', data, **auth(self.user))
        self.assertIn('social_status', response.json())

        response = self.client.post('/api/v1/me/startup/', {**data, 'logo': _png('logo.png'),
                                                            'social_status': 'unemployed'},
                                    **auth(self.user))
        self.assertEqual(response.status_code, 201, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.social_status, 'unemployed')

    def test_working_status_drops_education_place(self):
        self.add(social_status='employed', education_place="SamDU")
        self.user.refresh_from_db()
        self.assertEqual((self.user.social_status, self.user.education_place), ('employed', ''))

    def test_profile_shows_and_edits_status(self):
        self.add(social_status='school', education_place="12-maktab")
        me = self.client.get('/api/v1/auth/me/', **auth(self.user)).json()
        self.assertEqual(me['social_status_display'], "Maktab o'quvchisi")
        self.assertEqual(me['education_place'], "12-maktab")

        # O'qish joyi saqlangan — maktabni bitirib talaba bo'lsa, holatni almashtirsa bo'ladi
        switched = self.client.patch('/api/v1/auth/me/', {'social_status': 'student'},
                                     content_type='application/json', **auth(self.user))
        self.assertEqual(switched.status_code, 200, switched.content)

        response = self.client.patch('/api/v1/auth/me/',
                                     {'social_status': 'employed'},
                                     content_type='application/json', **auth(self.user))
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.education_place, '')

        empty = self.client.patch('/api/v1/auth/me/',
                                  {'social_status': 'student', 'education_place': ''},
                                  content_type='application/json', **auth(self.user))
        self.assertEqual(empty.status_code, 400)

    def test_panel_filters_users_and_startups(self):
        self.add(social_status='student', education_place="SamDU")
        other = User.objects.create_user(email='o@test.uz', full_name="Bo'sh", role='yosh')

        users = self.client.get('/api/v1/panel/users/?holat=student', **auth(self.admin)).json()
        self.assertEqual([row['id'] for row in users['results']], [self.user.pk])
        self.assertEqual(users['results'][0]['education_place'], "SamDU")
        counts = {row['value']: row['count'] for row in users['social_statuses']}
        self.assertEqual(counts['student'], 1)
        self.assertGreaterEqual(counts['yoq'], 1)

        missing = self.client.get('/api/v1/panel/users/?holat=yoq', **auth(self.admin)).json()
        self.assertIn(other.pk, [row['id'] for row in missing['results']])

        startups = self.client.get('/api/v1/panel/startups/?holat=student',
                                   **auth(self.admin)).json()
        self.assertEqual(startups['count'], 1)
        owner = startups['results'][0]['owner']
        self.assertEqual((owner['social_status_display'], owner['education_place']),
                         ("Talaba", "SamDU"))
        none = self.client.get('/api/v1/panel/startups/?holat=employed', **auth(self.admin)).json()
        self.assertEqual(none['count'], 0)

        detail = self.client.get(f'/api/v1/panel/users/{self.user.pk}/', **auth(self.admin)).json()
        self.assertEqual(detail['user']['social_status_display'], "Talaba")
