"""Startap va tadbirkorlar ro'yxati: hammasi sahifalab chiqadi, filtr sonlari butun bazadan."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.business.models import BusinessProfile
from apps.core.constants import Status
from apps.startups.models import Startup


def startup(index, sphere, stage):
    return Startup.objects.create(name=f"Startap {index}", sphere=sphere, stage=stage,
                                  about="Tavsif", full_name="Egasi", status=Status.APPROVED,
                                  is_public=True)


class DirectoryListTests(TestCase):
    def test_all_startups_are_reachable_and_counts_are_complete(self):
        for index in range(27):
            startup(index, 'edtech' if index < 15 else 'it', 'idea' if index % 3 else 'mvp')
        Startup.objects.create(name="Yashirin", sphere='edtech', stage='idea', about="T",
                               full_name="E", status=Status.PENDING)

        first = self.client.get('/api/v1/startups/').json()
        self.assertEqual((first['count'], first['total'], len(first['results'])), (27, 27, 24))
        second = self.client.get('/api/v1/startups/?page=2').json()
        self.assertEqual(len(second['results']), 3)

        spheres = {row['value']: row['count'] for row in first['facets']['soha']}
        self.assertEqual(spheres, {'edtech': 15, 'it': 12})

        # Soha tanlansa: ro'yxat va bosqich sonlari shu soha ichida, soha sonlari esa to'liq
        edtech = self.client.get('/api/v1/startups/?soha=edtech').json()
        self.assertEqual((edtech['count'], edtech['total']), (15, 27))
        stages = {row['value']: row['count'] for row in edtech['facets']['bosqich']}
        self.assertEqual(sum(stages.values()), 15)
        self.assertEqual({row['value']: row['count'] for row in edtech['facets']['soha']}, spheres)

    def test_businesses_have_facets_too(self):
        for index in range(26):
            owner = get_user_model().objects.create_user(email=f'b{index}@test.uz', full_name="E")
            BusinessProfile.objects.create(user=owner, name=f"Biznes {index}", sphere='xizmat',
                                           region='samarqand' if index < 20 else 'buxoro',
                                           description="T", status=Status.APPROVED,
                                           is_public=True)
        data = self.client.get('/api/v1/businesses/?hudud=buxoro').json()
        self.assertEqual((data['count'], data['total']), (6, 26))
        regions = {row['value']: row['count'] for row in data['facets']['hudud']}
        self.assertEqual(regions, {'samarqand': 20, 'buxoro': 6})
