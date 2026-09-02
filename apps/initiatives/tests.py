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

    def test_problem_listed_for_youth(self):
        url = reverse('initiatives:youth_problem', kwargs={'problem_id': self.problem.pk})
        response = self.client.get(url)
        self.assertContains(response, "MedService")
        self.assertContains(response, "Navbat 2 soat")

    def test_submit_solution(self):
        url = reverse('initiatives:youth_problem', kwargs={'problem_id': self.problem.pk})
        response = self.client.post(url, {
            'problem_id': self.problem.pk,
            'author_name': "Yosh Dasturchi",
            'title': "Onlayn navbat boti",
            'description': "Telegram bot orqali navbat olish tizimi.",
            'technologies': "Python, aiogram",
        })
        self.assertRedirects(response, reverse('initiatives:solution_success'))
        self.assertEqual(Solution.objects.count(), 1)
        self.assertEqual(self.problem.solutions_count, 1)

    def test_selected_problem_page(self):
        url = reverse('initiatives:youth_problem', kwargs={'problem_id': self.problem.pk})
        response = self.client.get(url)
        self.assertContains(response, "Tanlangan muammo")
        self.assertContains(response, "Yechim nomi")
