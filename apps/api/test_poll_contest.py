"""Yetakchilar tanlovi: yo'nalishlar, havola orqali ariza, tasdiqlash va ovoz."""

import json
import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from apps.content.models import Poll, PollCategory, PollOption, PollVote

from . import poll_views
from .auth_views import tokens_for

User = get_user_model()
MEDIA = tempfile.mkdtemp()

NOMINATIONS = [
    "Eng ko'p yoshni ish bilan ta'minlagan yetakchi",
    "Eng ko'p yoshni tadbirkorlikka jalb qilgan yetakchi",
    "Eng faol yoshlar yetakchisi",
]


def photo(name='p.png'):
    buffer = BytesIO()
    Image.new('RGB', (20, 20), '#3a8').save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


@override_settings(SITE_URL='https://samarqandyoshlari.uz', MEDIA_ROOT=MEDIA)
class ContestTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x',
                                                   full_name="Admin", telegram_id=500)
        self.users = [
            User.objects.create_user(email=f'u{n}@test.uz', full_name=f"Yosh {n}",
                                     telegram_id=1000 + n, district='urgut')
            for n in range(3)
        ]

    # -- yordamchilar ---------------------------------------------------------

    def create(self, **fields):
        categories = [{'key': f'k{n}', 'title': title, 'emoji': '🏆'}
                      for n, title in enumerate(NOMINATIONS)]
        data = {'title': "Yoshlar yetakchilari tanlovi", 'is_active': 'true',
                'show_results': 'true', 'podium_min_votes': '1', 'apply_open': 'true',
                'categories': json.dumps(categories), 'options': '[]', **fields}
        response = self.client.post('/api/v1/panel/polls/', data, **auth(self.admin))
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def poll(self):
        return Poll.objects.get(title="Yoshlar yetakchilari tanlovi")

    def category(self, index):
        return PollCategory.objects.get(title=NOMINATIONS[index])

    def apply(self, token=None, **fields):
        token = token or self.poll().apply_token
        data = {'name': "Aliyev Vali", 'mahalla': "Navbahor", 'district': 'urgut',
                'category': self.category(0).pk, 'phone': '+998 90 123 45 67',
                'photo': photo(), **fields}
        data = {key: value for key, value in data.items() if value is not None}
        return self.client.post(f'/api/v1/polls/ariza/{token}/', data)

    def approve(self, option, **extra):
        return self.client.patch(
            f'/api/v1/panel/polls/{option.poll_id}/arizalar/{option.pk}/',
            {'status': 'approved', **extra}, content_type='application/json',
            **auth(self.admin))

    def vote(self, user, option):
        return self.client.post(f'/api/v1/polls/{self.poll().slug}/vote/',
                                {'option': option.pk}, content_type='application/json',
                                **auth(user))

    def candidate(self, name, index, phone):
        response = self.apply(name=name, category=self.category(index).pk, phone=phone)
        self.assertEqual(response.status_code, 201, response.content)
        option = PollOption.objects.get(name=name)
        self.assertEqual(self.approve(option).status_code, 200)
        return option

    # -- panel: yaratish ------------------------------------------------------

    def test_poll_made_in_django_admin_also_gets_link(self):
        poll = Poll.objects.create(title="Admin orqali")
        self.assertTrue(poll.apply_token)
        self.assertTrue(poll.apply_open)

    def test_contest_starts_without_candidates_and_gets_link(self):
        data = self.create()
        self.assertEqual([c['title'] for c in data['categories']], NOMINATIONS)
        self.assertEqual(data['options_count'], 0)
        self.assertTrue(data['apply_open'])
        token = self.poll().apply_token
        self.assertTrue(token and len(token) >= 20)
        self.assertEqual(data['apply_url'], f'/sorovnomalar/ariza/{token}')

    def test_new_link_replaces_old_one(self):
        self.create()
        old = self.poll().apply_token
        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/',
                                     {'new_apply_link': True}, content_type='application/json',
                                     **auth(self.admin))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotEqual(self.poll().apply_token, old)
        self.assertEqual(self.client.get(f'/api/v1/polls/ariza/{old}/').status_code, 404)

    def test_public_poll_never_exposes_apply_token(self):
        self.create()
        token = self.poll().apply_token
        for url in ('/api/v1/polls/', f'/api/v1/polls/{self.poll().slug}/'):
            self.assertNotIn(token, self.client.get(url).content.decode())

    # -- ariza ----------------------------------------------------------------

    def test_apply_form_lists_nominations_and_districts(self):
        self.create()
        response = self.client.get(f'/api/v1/polls/ariza/{self.poll().apply_token}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['accepts'])
        self.assertEqual([c['title'] for c in data['categories']], NOMINATIONS)
        self.assertIn({'value': 'urgut', 'label': "Urgut tumani"}, data['districts'])

    def test_wrong_token_is_404(self):
        self.create()
        self.assertEqual(self.client.get('/api/v1/polls/ariza/yoq-kalit/').status_code, 404)
        self.assertEqual(self.apply(token='yoq-kalit').status_code, 404)
        self.assertFalse(PollOption.objects.exists())

    def test_application_waits_for_approval(self):
        self.create()
        response = self.apply(note="200 yoshni ishga joylashtirdim")
        self.assertEqual(response.status_code, 201, response.content)

        option = PollOption.objects.get()
        self.assertEqual(option.status, PollOption.Status.PENDING)
        self.assertEqual(option.phone, '+998901234567')
        self.assertEqual(option.category, self.category(0))
        self.assertTrue(option.photo)

        # Saytda hali yo'q, ovoz ham berib bo'lmaydi
        detail = self.client.get(f'/api/v1/polls/{self.poll().slug}/').json()
        self.assertEqual(detail['options'], [])
        self.assertEqual(self.vote(self.users[0], option).status_code, 400)

        # Tasdiqlangach chiqadi — telefon esa saytda ko'rinmaydi
        self.assertEqual(self.approve(option).status_code, 200)
        detail = self.client.get(f'/api/v1/polls/{self.poll().slug}/').json()
        self.assertEqual([o['name'] for o in detail['options']], ["Aliyev Vali"])
        self.assertNotIn('phone', detail['options'][0])
        self.assertNotIn('998901234567', json.dumps(detail))

    def test_application_requires_every_field(self):
        self.create()
        for field, word in [('name', "Ism"), ('mahalla', "Mahalla"), ('district', "Tuman"),
                            ('category', "Yo'nalish"), ('phone', "Telefon"), ('photo', "Rasm")]:
            response = self.apply(**{field: None})
            self.assertEqual(response.status_code, 400, field)
            self.assertIn(word.lower(), response.json()['detail'].lower(), field)
        self.assertFalse(PollOption.objects.exists())

    def test_category_must_belong_to_this_poll(self):
        self.create()
        other = Poll.objects.create(title="Boshqa")
        alien = PollCategory.objects.create(poll=other, title="Begona")
        self.assertEqual(self.apply(category=alien.pk).status_code, 400)

    def test_duplicate_application_in_same_nomination(self):
        self.create()
        self.assertEqual(self.apply().status_code, 201)
        response = self.apply(phone='998901234567')
        self.assertEqual(response.status_code, 409)
        # Boshqa yo'nalishga — mumkin
        self.assertEqual(self.apply(category=self.category(1).pk).status_code, 201)

    def test_closed_applications(self):
        self.create()
        self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/', {'apply_open': False},
                          content_type='application/json', **auth(self.admin))
        token = self.poll().apply_token
        self.assertFalse(self.client.get(f'/api/v1/polls/ariza/{token}/').json()['accepts'])
        self.assertEqual(self.apply(token=token).status_code, 400)
        self.assertFalse(PollOption.objects.exists())

    def test_honeypot_saves_nothing(self):
        self.create()
        self.assertEqual(self.apply(website='http://spam').status_code, 201)
        self.assertFalse(PollOption.objects.exists())

    @override_settings(CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'apply-test'}})
    def test_applications_are_rate_limited(self):
        self.create()
        with mock.patch.object(poll_views.ApplyThrottle, 'THROTTLE_RATES',
                               {'poll_apply': '2/hour'}):
            codes = [self.apply(phone=f'+99890000000{n}').status_code for n in range(3)]
        self.assertEqual(codes, [201, 201, 429])

    # -- panel: arizalar ------------------------------------------------------

    def test_applications_panel_is_admin_only(self):
        self.create()
        self.apply()
        option = PollOption.objects.get()
        poll = self.poll()
        urls = [f'/api/v1/panel/polls/{poll.pk}/arizalar/',
                f'/api/v1/panel/polls/{poll.pk}/arizalar/{option.pk}/']
        for user_auth in ({}, auth(self.users[0])):
            self.assertEqual(self.client.get(urls[0], **user_auth).status_code, 404)
            response = self.client.patch(urls[1], {'status': 'approved'},
                                         content_type='application/json', **user_auth)
            self.assertIn(response.status_code, (401, 404))
            self.assertIn(self.client.delete(urls[1], **user_auth).status_code, (401, 404))
        option.refresh_from_db()
        self.assertEqual(option.status, PollOption.Status.PENDING)

    def test_admin_lists_rejects_and_deletes_applications(self):
        self.create()
        self.apply()
        self.apply(name="Karimova Zuhra", phone='+998911112233')
        poll = self.poll()

        data = self.client.get(f'/api/v1/panel/polls/{poll.pk}/arizalar/', **auth(self.admin)).json()
        self.assertEqual(data['counts']['pending'], 2)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['results'][0]['phone'], '+998911112233')

        first, second = PollOption.objects.order_by('pk')
        response = self.client.patch(f'/api/v1/panel/polls/{poll.pk}/arizalar/{first.pk}/',
                                     {'status': 'rejected'}, content_type='application/json',
                                     **auth(self.admin))
        self.assertEqual(response.json()['counts'], {'pending': 1, 'approved': 0, 'rejected': 1})

        response = self.client.delete(f'/api/v1/panel/polls/{poll.pk}/arizalar/{second.pk}/',
                                      **auth(self.admin))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PollOption.objects.filter(pk=second.pk).exists())

        # Panel ro'yxatida kutilayotganlar soni
        listing = self.client.get('/api/v1/panel/polls/', **auth(self.admin)).json()
        self.assertEqual(listing['results'][0]['pending_count'], 0)

    def test_admin_can_move_application_to_other_nomination(self):
        self.create()
        self.apply()
        option = PollOption.objects.get()
        response = self.approve(option, category=self.category(2).pk)
        self.assertEqual(response.status_code, 200)
        option.refresh_from_db()
        self.assertEqual(option.category, self.category(2))

    # -- ovoz -----------------------------------------------------------------

    def test_one_vote_per_nomination_and_separate_rankings(self):
        self.create()
        vali = self.candidate("Aliyev Vali", 0, '+998900000001')
        zuhra = self.candidate("Karimova Zuhra", 0, '+998900000002')
        sardor = self.candidate("Rasulov Sardor", 1, '+998900000003')

        self.assertEqual(self.vote(self.users[0], zuhra).status_code, 201)
        # Shu yo'nalishda ikkinchi ovoz — yo'q
        response = self.vote(self.users[0], vali)
        self.assertEqual(response.status_code, 409)
        self.assertIn("yo'nalishda", response.json()['detail'])
        # Boshqa yo'nalishda — bor
        response = self.vote(self.users[0], sardor)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sorted(response.json()['my_votes']), sorted([zuhra.pk, sardor.pk]))
        self.assertEqual(self.vote(self.users[1], zuhra).status_code, 201)

        detail = self.client.get(f'/api/v1/polls/{self.poll().slug}/',
                                 **auth(self.users[0])).json()
        rows = {o['name']: o for o in detail['options']}
        # O'rin va foiz — har yo'nalish ichida
        self.assertEqual(rows["Karimova Zuhra"]['rank'], 1)
        self.assertEqual(rows["Karimova Zuhra"]['percent'], 100.0)
        self.assertEqual(rows["Aliyev Vali"]['rank'], 2)
        self.assertEqual(rows["Rasulov Sardor"]['rank'], 1)
        self.assertEqual(rows["Rasulov Sardor"]['votes'], 1)
        totals = {c['title']: c['total_votes'] for c in detail['categories']}
        self.assertEqual(totals[NOMINATIONS[0]], 2)
        self.assertEqual(totals[NOMINATIONS[1]], 1)
        self.assertEqual(detail['total_votes'], 3)
        self.assertEqual(sorted(detail['my_votes']), sorted([zuhra.pk, sardor.pk]))

        vote = PollVote.objects.get(user=self.users[0], option=sardor)
        self.assertEqual(vote.category, self.category(1))

    def test_voted_candidate_cannot_be_rejected_or_moved(self):
        self.create()
        vali = self.candidate("Aliyev Vali", 0, '+998900000001')
        self.vote(self.users[0], vali)
        url = f'/api/v1/panel/polls/{vali.poll_id}/arizalar/{vali.pk}/'
        for payload in ({'status': 'rejected'}, {'category': self.category(1).pk}):
            response = self.client.patch(url, payload, content_type='application/json',
                                         **auth(self.admin))
            self.assertEqual(response.status_code, 400, payload)
        self.assertEqual(self.client.delete(url, **auth(self.admin)).status_code, 400)
        self.assertTrue(PollVote.objects.filter(option=vali).exists())

    def test_editing_poll_keeps_pending_applications(self):
        data = self.create()
        self.apply()
        vali = self.candidate("Karimova Zuhra", 1, '+998900000009')
        # Admin formani saqlaydi: ro'yxatda faqat tasdiqlangan nomzod bor
        editable = [{'id': row['id'], 'name': row['name'], 'category': str(row['category'])}
                    for row in self.client.get('/api/v1/panel/polls/', **auth(self.admin))
                    .json()['results'][0]['editable']]
        categories = [{'id': c['id'], 'title': c['title'], 'emoji': c['emoji']}
                      for c in data['categories']]
        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/', {
            'options': editable, 'categories': categories,
        }, content_type='application/json', **auth(self.admin))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(PollOption.objects.filter(status='pending').count(), 1)
        self.assertTrue(PollOption.objects.filter(pk=vali.pk).exists())

    def test_admin_added_candidate_needs_nomination(self):
        data = self.create()
        category = data['categories'][0]['id']
        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/', {
            'options': [{'name': "Yangi nomzod"}],
        }, content_type='application/json', **auth(self.admin))
        self.assertEqual(response.status_code, 400)
        self.assertIn("yo'nalish", response.json()['options'])

        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/', {
            'options': [{'name': "Yangi nomzod", 'category': str(category)}],
        }, content_type='application/json', **auth(self.admin))
        self.assertEqual(response.status_code, 200, response.content)
        option = PollOption.objects.get(name="Yangi nomzod")
        self.assertEqual(option.status, PollOption.Status.APPROVED)
        self.assertEqual(option.category_id, category)

    def test_nomination_with_candidates_cannot_be_removed(self):
        data = self.create()
        self.apply()
        kept = [{'id': c['id'], 'title': c['title']} for c in data['categories'][1:]]
        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/',
                                     {'categories': kept}, content_type='application/json',
                                     **auth(self.admin))
        self.assertEqual(response.status_code, 400)
        self.assertIn("nomzod", response.json()['categories'])
        self.assertEqual(PollCategory.objects.count(), 3)

    def test_list_card_shows_leader_of_each_nomination(self):
        self.create()
        vali = self.candidate("Aliyev Vali", 0, '+998900000001')
        self.candidate("Karimova Zuhra", 0, '+998900000002')
        self.candidate("Rasulov Sardor", 1, '+998900000003')
        self.vote(self.users[0], vali)
        card = self.client.get('/api/v1/polls/').json()['results'][0]
        self.assertEqual([o['name'] for o in card['options']], ["Aliyev Vali", "Rasulov Sardor"])
        self.assertEqual(card['options_count'], 3)
