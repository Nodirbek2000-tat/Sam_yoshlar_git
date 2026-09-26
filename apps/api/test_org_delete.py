"""Panel: tashkilotni o'chirish — muammolari, takliflari va kirish hisobi bilan."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.initiatives.models import Organization, Problem, Solution

from .auth_views import tokens_for

User = get_user_model()


class OrganizationDeleteTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")
        self.auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(admin)['access']}"}
        self.account = User.objects.create_user(email='org@test.uz', password='x',
                                                full_name="Org", role='organization',
                                                telegram_id=555)
        self.org = Organization.objects.create(user=self.account, name="AgroTech", sphere='it',
                                               contact_person="Ali", phone='+998901112233')
        problem = Problem.objects.create(organization=self.org, category='main',
                                         description="Muammo")
        Solution.objects.create(problem=problem, author_name="Yosh", title="Yechim",
                                description="Taklif")

    def test_organization_is_deleted_with_everything(self):
        response = self.client.delete(f'/api/v1/panel/organizations/{self.org.pk}/', **self.auth)
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual((data['problems'], data['solutions']), (1, 1))
        self.assertTrue(data['account_deleted'])
        self.assertFalse(Organization.objects.exists())
        self.assertFalse(Problem.objects.exists())
        self.assertFalse(Solution.objects.exists())
        # O'chirilgan tashkilot endi kira olmaydi
        self.assertFalse(User.objects.filter(pk=self.account.pk).exists())

    def test_shared_or_admin_account_is_kept(self):
        Organization.objects.create(user=self.account, name="Ikkinchi", sphere='it',
                                    contact_person="Ali", phone='+998901112233')
        data = self.client.delete(f'/api/v1/panel/organizations/{self.org.pk}/',
                                  **self.auth).json()
        self.assertFalse(data['account_deleted'])
        self.assertTrue(User.objects.filter(pk=self.account.pk).exists())

    def test_only_panel_admin(self):
        user = User.objects.create_user(email='y@test.uz', full_name="Y")
        auth = {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}
        response = self.client.delete(f'/api/v1/panel/organizations/{self.org.pk}/', **auth)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Organization.objects.exists())
