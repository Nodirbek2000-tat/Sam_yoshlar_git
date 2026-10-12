"""Tashabbusda tuman va mahalla: birinchi marta so'raladi, keyin hisobdan olinadi."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.mahalla import mahalla_key
from apps.initiatives.models import Initiative, InitiativeVote

from .auth_views import tokens_for

User = get_user_model()


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


class InitiativeMahallaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='y@test.uz', full_name="Yosh Bola",
                                             role='yosh', is_verified=True)
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x', full_name="A")

    def submit(self, user=None, **extra):
        data = {'direction': 'edu', 'kind': 'idea', 'title': "Kutubxona kerak",
                'description': "Mahallamizda yoshlar uchun kutubxona ochish kerak.",
                'author_name': "Yosh Bola", **extra}
        return self.client.post('/api/v1/initiatives/', data, content_type='application/json',
                                **auth(user or self.user))

    def test_first_initiative_asks_district_and_mahalla(self):
        response = self.submit()
        self.assertEqual(response.status_code, 400)
        self.assertIn('district', response.json())
        self.assertIn('mahalla', response.json())

        self.assertIn('district', self.submit(district='toshkent', mahalla="Bog'ishamol").json())
        self.assertIn('mahalla', self.submit(district='urgut', mahalla="ab").json())

        response = self.submit(district='urgut', mahalla="  Bog'ishamol   MFY ")
        self.assertEqual(response.status_code, 201, response.content)
        item = Initiative.objects.get(pk=response.json()['id'])
        self.assertEqual((item.region, item.district, item.mahalla),
                         ('samarqand', "Urgut tumani", "Bog'ishamol MFY"))

        self.user.refresh_from_db()
        self.assertEqual((self.user.district, self.user.mahalla), ("Urgut tumani", "Bog'ishamol MFY"))

        # Ikkinchisida so'ralmaydi — hisobdagisi olinadi
        second = self.submit(title="Sport maydoni kerak")
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(Initiative.objects.get(pk=second.json()['id']).mahalla, "Bog'ishamol MFY")

    def test_user_from_bot_with_district_only_types_mahalla(self):
        self.user.district = "Payariq tumani"
        self.user.save()
        response = self.submit(mahalla="Navbahor")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Initiative.objects.get().district, "Payariq tumani")

    def test_voting_never_asks_mahalla(self):
        author = User.objects.create_user(email='m@test.uz', full_name="Muallif",
                                          district="Urgut tumani", mahalla="Bog'ishamol")
        item = Initiative.objects.create(direction='edu', kind='idea', title="Kutubxona",
                                         description="Matn", author=author, author_name="M",
                                         district="Urgut tumani", mahalla="Bog'ishamol")
        response = self.client.post(f'/api/v1/initiatives/{item.pk}/vote/', **auth(self.user))
        self.assertIn(response.status_code, (200, 201), response.content)

    def test_mahalla_key_groups_spellings(self):
        keys = {mahalla_key(name) for name in
                ["Bog'ishamol MFY", "bogishamol mfy", "Bog‘ishamol mahallasi", "BOG'ISHAMOL M.F.Y."]}
        self.assertEqual(keys, {'bogishamol'})

    def test_panel_region_stats(self):
        people = [("Urgut tumani", "Bog'ishamol MFY"), ("Urgut tumani", "bogishamol mfy"),
                  ("Urgut tumani", "Navbahor"), ("Urgut tumani", ""), ("Payariq tumani", "Gulzor")]
        users = [User.objects.create_user(email=f'u{i}@test.uz', full_name=f"U{i}",
                                          district=d, mahalla=m) for i, (d, m) in enumerate(people)]
        item = Initiative.objects.create(direction='edu', kind='idea', title="Bog'",
                                         description="Matn", author=users[0], author_name="U0",
                                         district="Urgut tumani", mahalla="Bog'ishamol MFY")
        # Eski tashabbus: hududi yozilmagan — muallifniki olinadi
        Initiative.objects.create(direction='edu', kind='idea', title="Eski",
                                  description="Matn", author=users[4], author_name="U4")
        InitiativeVote.objects.create(initiative=item, user=users[1])
        InitiativeVote.objects.create(initiative=item, user=users[4])

        self.assertEqual(self.client.get('/api/v1/panel/hududlar/', **auth(self.user)).status_code,
                         404)
        data = self.client.get('/api/v1/panel/hududlar/', **auth(self.admin)).json()

        urgut = next(row for row in data['districts'] if row['value'] == 'urgut')
        self.assertEqual((urgut['users'], urgut['initiatives'], urgut['votes']), (4, 1, 1))
        self.assertEqual(urgut['without_mahalla']['users'], 1)
        self.assertEqual(urgut['mahalla_count'], 2)
        bogishamol = urgut['mahallas'][0]
        self.assertEqual((bogishamol['users'], bogishamol['initiatives'], bogishamol['votes']),
                         (2, 1, 1))
        self.assertIn(bogishamol['name'], ("Bog'ishamol MFY", "bogishamol mfy"))

        payariq = next(row for row in data['districts'] if row['value'] == 'payariq')
        self.assertEqual((payariq['users'], payariq['initiatives'], payariq['votes']), (1, 1, 1))
        self.assertEqual(data['totals']['users'], 6)   # + hududsiz oddiy foydalanuvchi
        self.assertEqual(data['unknown']['users'], 1)
