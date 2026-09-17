from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from .models import PROBLEM_QUESTIONS, Organization, Problem, ProblemCategory, Solution


class OrganizationFormTests(TestCase):
    def _base_data(self):
        return {
            'name': "Test tashkilot",
            'sphere': 'talim',
            'contact_person': "Aziz Rahimov",
            'phone': '+998901112233',
        }

    def test_all_eleven_steps_rendered(self):
        response = self.client.get(reverse('initiatives:organizations'))
        self.assertEqual(response.status_code, 200)
        for item in PROBLEM_QUESTIONS:
            self.assertContains(response, escape(item['question'][:40]))

    def test_submission_creates_problems(self):
        data = self._base_data()
        data['problem_bottlenecks'] = "Hujjat aylanishi juda sekin."
        data['problem_technology'] = "Hamma hisobot Excel'da yuritiladi."
        data['problem_main'] = "Navbat tizimi yo'q."

        response = self.client.post(reverse('initiatives:organizations'), data)
        self.assertRedirects(response, reverse('initiatives:organization_success'))

        organization = Organization.objects.get(name="Test tashkilot")
        self.assertEqual(organization.problems.count(), 3)
        categories = set(organization.problems.values_list('category', flat=True))
        self.assertEqual(categories, {ProblemCategory.BOTTLENECKS, ProblemCategory.TECHNOLOGY,
                                      ProblemCategory.MAIN})

    def test_empty_answers_rejected(self):
        response = self.client.post(reverse('initiatives:organizations'), self._base_data())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Organization.objects.count(), 0)


class SolutionTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="MedService", sphere='tibbiyot', contact_person="Nodira", phone='+998900000000',
        )
        self.problem = Problem.objects.create(
            organization=self.organization, category=ProblemCategory.BOTTLENECKS,
            description="Navbat 2 soat.",
        )

    def _detail_url(self):
        return reverse('initiatives:problem_detail', kwargs={'pk': self.problem.pk})

    def test_problem_listed_for_youth(self):
        response = self.client.get(reverse('initiatives:problems'))
        self.assertContains(response, "MedService")
        self.assertContains(response, "Navbat 2 soat")

    def test_problem_detail_open_for_guests(self):
        """Ko'rish hamma uchun ochiq."""
        response = self.client.get(self._detail_url())
        self.assertContains(response, "MedService")
        self.assertContains(response, "Navbat 2 soat")
        self.assertContains(response, "Taklif berish uchun ro")

    def test_guest_cannot_submit_solution(self):
        response = self.client.post(self._detail_url(), {
            'author_name': "Mehmon",
            'title': "Yechim",
            'description': "Tavsif.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])
        self.assertEqual(Solution.objects.count(), 0)

    def test_submit_solution(self):
        User = get_user_model()
        user = User.objects.create_user(email='yosh@samarqandyoshlari.uz', password='Parol2026!',
                                        full_name="Yosh Dasturchi")
        self.client.force_login(user)

        response = self.client.post(self._detail_url(), {
            'author_name': "Yosh Dasturchi",
            'title': "Onlayn navbat boti",
            'description': "Telegram bot orqali navbat olish tizimi.",
            'technologies': "Python, aiogram",
        })
        self.assertRedirects(response, reverse('initiatives:solution_success'))
        self.assertEqual(Solution.objects.count(), 1)
        self.assertEqual(self.problem.solutions_count, 1)
        self.assertEqual(Solution.objects.first().author, user)

    def test_selected_problem_page(self):
        User = get_user_model()
        user = User.objects.create_user(email='yosh2@samarqandyoshlari.uz', password='Parol2026!')
        self.client.force_login(user)
        response = self.client.get(self._detail_url())
        self.assertContains(response, "Yechimingizni taklif qiling")
        self.assertContains(response, "Yechim nomi")

    def test_old_url_redirects(self):
        response = self.client.get(reverse('initiatives:youth_problem',
                                           kwargs={'pk': self.problem.pk}))
        self.assertRedirects(response, self._detail_url())
