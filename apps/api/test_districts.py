"""Tuman / shahar: kabinetda ko'rinadi, o'zgartiriladi va panelda saralanadi."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from .auth_views import tokens_for

User = get_user_model()


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


class ProfileDistrictTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='y@test.uz', full_name="Yosh", role='yosh',
                                             age=22, is_verified=True, study_location='uz')

    def patch(self, data, user=None):
        return self.client.patch('/api/v1/auth/me/', data, content_type='application/json',
                                 **auth(user or self.user))

    def test_reference_lists_all_districts(self):
        data = self.client.get('/api/v1/reference/').json()
        self.assertEqual(len(data['districts']), 16)
        self.assertEqual(data['districts'][0], {'value': 'samarqand_shahri',
                                                'label': "Samarqand shahri"})

    def test_district_code_is_saved_as_name_with_region(self):
        response = self.patch({'district': 'urgut'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['district'], "Urgut tumani")
        self.assertEqual(response.json()['region'], 'samarqand')

    def test_unknown_district_rejected(self):
        response = self.patch({'district': "Chilonzor"})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.district, '')

    def test_organization_role_cannot_be_chosen(self):
        self.assertEqual(self.patch({'role': 'organization'}).status_code, 400)
        self.assertEqual(self.patch({'role': 'admin'}).status_code, 400)

    def test_organization_cannot_leave_its_role(self):
        org = User.objects.create_user(email='o@test.uz', full_name="Org", role='organization',
                                       is_verified=True)
        self.assertEqual(self.patch({'role': 'yosh'}, user=org).status_code, 400)
        # O'z rolini qayta yuborishi xato emas
        self.assertEqual(self.patch({'role': 'organization'}, user=org).status_code, 200)


class PanelDistrictFilterTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x',
                                                   full_name="Admin")
        User.objects.create_user(email='1@test.uz', full_name="Bir", role='yosh',
                                 district="Urgut tumani")
        User.objects.create_user(email='2@test.uz', full_name="Ikki", role='yosh',
                                 district="Urgut tumani")
        User.objects.create_user(email='3@test.uz', full_name="Uch", role='startupper',
                                 district="Samarqand shahri")
        User.objects.create_user(email='4@test.uz', full_name="To'rt", role='yosh')
        # Eskidan qo'lda yozilgan, ro'yxatda yo'q tuman
        User.objects.create_user(email='5@test.uz', full_name="Besh", role='yosh',
                                 district="asda")

    def users(self, **params):
        return self.client.get('/api/v1/panel/users/', params, **auth(self.admin)).json()

    def test_filter_by_district(self):
        data = self.users(tuman='urgut')
        self.assertEqual(sorted(row['full_name'] for row in data['results']), ["Bir", "Ikki"])
        self.assertEqual(data['results'][0]['district'], "Urgut tumani")

    def test_counts_per_district(self):
        data = self.users()
        counts = {row['value']: row['count'] for row in data['districts']}
        self.assertEqual(counts['urgut'], 2)
        self.assertEqual(counts['samarqand_shahri'], 1)
        self.assertEqual(counts['toyloq'], 0)
        # Admin + tumansiz yosh + noma'lum tuman — hech kim tushib qolmaydi
        self.assertEqual(data['without_district'], 3)
        total = sum(row['count'] for row in data['districts']) + data['without_district']
        self.assertEqual(total, data['count'])

    def test_counts_follow_role_filter(self):
        data = self.users(rol='yosh')
        counts = {row['value']: row['count'] for row in data['districts']}
        self.assertEqual(counts['urgut'], 2)
        self.assertEqual(counts['samarqand_shahri'], 0)

    def test_users_without_district(self):
        data = self.users(tuman='yoq', rol='yosh')
        self.assertEqual(sorted(row['full_name'] for row in data['results']), ["Besh", "To'rt"])

    def test_unknown_district_value_is_ignored(self):
        self.assertEqual(self.users(tuman='nomalum')['count'], 6)
