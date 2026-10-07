"""So'rovnomalar: panelda yaratish, saytda ovoz berish, reyting va natijalar."""

import json
import os
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from apps.accounts.models import BotPost, BotSetting
from apps.content.models import Poll, PollOption, PollVote

from .auth_views import tokens_for

User = get_user_model()
MEDIA = tempfile.mkdtemp()


def photo(name='p.png'):
    buffer = BytesIO()
    Image.new('RGB', (20, 20), '#3a8').save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def auth(user):
    return {'HTTP_AUTHORIZATION': f"Bearer {tokens_for(user)['access']}"}


@override_settings(SITE_URL='https://samarqandyoshlari.uz', MEDIA_ROOT=MEDIA)
class PollTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_superuser(email='a@test.uz', password='x',
                                                   full_name="Admin", telegram_id=500)
        self.users = [
            User.objects.create_user(email=f'u{n}@test.uz', full_name=f"Yosh {n}",
                                     telegram_id=1000 + n, district='urgut')
            for n in range(4)
        ]

    # -- yordamchilar ---------------------------------------------------------

    def create(self, options=None, **fields):
        options = options or [
            {'key': 'a', 'name': "Aliyev Vali", 'mahalla': "Navbahor", 'district': 'urgut'},
            {'key': 'b', 'name': "Karimova Zuhra", 'mahalla': "Bog'ishamol",
             'district': 'samarqand_shahri'},
            {'key': 'c', 'name': "Rasulov Sardor", 'mahalla': "Ipakchi"},
        ]
        data = {'title': "Eng yaxshi mahalla yetakchisi", 'description': "Ovoz bering",
                'is_active': 'true', 'show_results': 'true',
                'options': json.dumps(options), **fields}
        return self.client.post('/api/v1/panel/polls/', data, **auth(self.admin))

    def poll(self):
        return Poll.objects.get(title="Eng yaxshi mahalla yetakchisi")

    def option(self, name):
        return PollOption.objects.get(name=name)

    def vote(self, user, option, slug=None):
        slug = slug or self.poll().slug
        return self.client.post(f'/api/v1/polls/{slug}/vote/', {'option': option.pk},
                                content_type='application/json', **auth(user))

    # -- panel ----------------------------------------------------------------

    def test_admin_creates_poll_with_options_and_photo(self):
        response = self.create(photo_a=photo())
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()

        self.assertEqual(data['options_count'], 3)
        self.assertEqual([o['name'] for o in data['editable']],
                         ["Aliyev Vali", "Karimova Zuhra", "Rasulov Sardor"])
        self.assertTrue(self.option("Aliyev Vali").photo)
        self.assertFalse(self.option("Rasulov Sardor").photo)
        self.assertEqual(data['editable'][1]['district_display'], "Samarqand shahri")

    def test_poll_needs_two_options(self):
        response = self.create(options=[{'name': "Yolg'iz"}])
        self.assertEqual(response.status_code, 400)
        self.assertIn("Kamida 2", response.json()['options'])
        self.assertFalse(Poll.objects.exists())

    def test_bad_option_rejects_everything(self):
        response = self.create(options=[{'name': "Bir"}, {'name': ""}])
        self.assertEqual(response.status_code, 400)
        self.assertIn("2-nomzod", response.json()['options'])
        self.assertFalse(Poll.objects.exists())
        self.assertFalse(PollOption.objects.exists())

    def test_panel_is_hidden_from_regular_users(self):
        response = self.client.get('/api/v1/panel/polls/', **auth(self.users[0]))
        self.assertEqual(response.status_code, 404)
        response = self.client.post('/api/v1/panel/polls/', {}, **auth(self.users[0]))
        self.assertEqual(response.status_code, 404)

    def test_editing_keeps_votes_and_removing_option_drops_its_votes(self):
        self.create()
        vali, zuhra, sardor = (self.option(n) for n in
                               ("Aliyev Vali", "Karimova Zuhra", "Rasulov Sardor"))
        self.vote(self.users[0], vali)
        self.vote(self.users[1], sardor)

        options = [{'id': vali.pk, 'name': "Aliyev Vali (rais)", 'mahalla': "Navbahor"},
                   {'id': zuhra.pk, 'name': "Karimova Zuhra"},
                   {'key': 'new', 'name': "Yangi Nomzod"}]
        url = f'/api/v1/panel/polls/{self.poll().pk}/'

        # Ovozi bor nomzod o'chmoqda — server avval rozilik so'raydi, hech narsa yozmaydi
        warned = self.client.patch(url, {'options': json.dumps(options)},
                                   content_type='application/json', **auth(self.admin))
        self.assertEqual(warned.status_code, 409)
        self.assertEqual(warned.json()['remove_voted'],
                         [{'id': sardor.pk, 'name': "Rasulov Sardor", 'votes': 1}])
        self.assertTrue(PollOption.objects.filter(pk=sardor.pk).exists())
        self.assertEqual(self.option("Aliyev Vali").name, "Aliyev Vali")

        # Boshqa nomzod uchun berilgan rozilik yetmaydi
        wrong = self.client.patch(url, {'options': json.dumps(options),
                                        'confirm_remove_voted': [vali.pk]},
                                  content_type='application/json', **auth(self.admin))
        self.assertEqual(wrong.status_code, 409)

        response = self.client.patch(url, {'options': json.dumps(options),
                                           'confirm_remove_voted': [sardor.pk]},
                                     content_type='application/json', **auth(self.admin))
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()

        self.assertEqual(data['total_votes'], 1)
        self.assertEqual(data['options'][0]['name'], "Aliyev Vali (rais)")
        self.assertEqual(data['options'][0]['votes'], 1)
        self.assertFalse(PollOption.objects.filter(pk=sardor.pk).exists())
        # Sardorga bergan odam endi qayta ovoz bera oladi
        self.assertEqual(self.vote(self.users[1], zuhra).status_code, 201)

    def test_removing_candidate_without_votes_needs_no_confirmation(self):
        self.create()
        vali, zuhra = self.option("Aliyev Vali"), self.option("Karimova Zuhra")
        options = [{'id': vali.pk, 'name': vali.name}, {'id': zuhra.pk, 'name': zuhra.name}]
        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/',
                                     {'options': json.dumps(options)},
                                     content_type='application/json', **auth(self.admin))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PollOption.objects.count(), 2)

    def test_error_names_the_row_number_shown_in_the_form(self):
        response = self.create(options=[{'name': "Bir", 'pos': 1}, {'name': "Ikki", 'pos': 2},
                                        {'name': "", 'mahalla': "Chorsu", 'pos': 4}])
        self.assertEqual(response.status_code, 400)
        self.assertIn("4-nomzod", response.json()['options'])

    def test_more_than_hundred_photos_in_one_save(self):
        options = [{'key': f'k{n}', 'name': f"Nomzod {n}"} for n in range(105)]
        photos = {f'photo_k{n}': photo(f'p{n}.png') for n in range(105)}
        response = self.create(options=options, **photos)
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertEqual(PollOption.objects.exclude(photo='').count(), 105)

    def test_foreign_option_id_is_rejected(self):
        self.create()
        other = Poll.objects.create(title="Boshqa so'rovnoma")
        stranger = PollOption.objects.create(poll=other, name="Begona")
        options = [{'id': stranger.pk, 'name': "Begona"}, {'name': "Bir"}]
        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/',
                                     {'options': json.dumps(options)},
                                     content_type='application/json', **auth(self.admin))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PollOption.objects.get(pk=stranger.pk).poll, other)

    def test_visibility_toggle_does_not_touch_options(self):
        self.create()
        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/',
                                     {'is_active': False}, content_type='application/json',
                                     **auth(self.admin))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PollOption.objects.count(), 3)
        self.assertEqual(self.client.get(f'/api/v1/polls/{self.poll().slug}/').status_code, 404)

    def test_delete_removes_poll_votes_and_photos(self):
        self.create(photo_a=photo())
        path = self.option("Aliyev Vali").photo.path
        self.vote(self.users[0], self.option("Aliyev Vali"))

        response = self.client.delete(f'/api/v1/panel/polls/{self.poll().pk}/',
                                      **auth(self.admin))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Poll.objects.exists())
        self.assertFalse(PollVote.objects.exists())
        self.assertFalse(os.path.exists(path))

    # -- ovoz berish ----------------------------------------------------------

    def test_guest_cannot_vote(self):
        self.create()
        response = self.client.post(f'/api/v1/polls/{self.poll().slug}/vote/',
                                    {'option': self.option("Aliyev Vali").pk},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertFalse(PollVote.objects.exists())

    def test_one_vote_per_person_and_live_ranking(self):
        self.create()
        vali, zuhra = self.option("Aliyev Vali"), self.option("Karimova Zuhra")

        response = self.vote(self.users[0], zuhra)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['my_vote'], zuhra.pk)
        self.assertEqual(response.json()['options'][0]['name'], "Karimova Zuhra")

        again = self.vote(self.users[0], vali)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()['my_vote'], zuhra.pk)

        self.vote(self.users[1], vali)
        self.vote(self.users[2], vali)
        data = self.client.get(f'/api/v1/polls/{self.poll().slug}/', **auth(self.users[2])).json()

        self.assertEqual(data['total_votes'], 3)
        self.assertEqual(data['my_vote'], vali.pk)
        first, second, third = data['options']
        self.assertEqual((first['name'], first['votes'], first['rank'], first['percent']),
                         ("Aliyev Vali", 2, 1, 66.7))
        self.assertEqual((second['name'], second['rank']), ("Karimova Zuhra", 2))
        self.assertEqual((third['votes'], third['rank']), (0, 3))

    def test_tied_candidates_share_a_place(self):
        self.create()
        self.vote(self.users[0], self.option("Aliyev Vali"))
        self.vote(self.users[1], self.option("Rasulov Sardor"))
        ranks = [o['rank'] for o in
                 self.client.get(f'/api/v1/polls/{self.poll().slug}/').json()['options']]
        self.assertEqual(ranks, [1, 1, 3])

    def test_malformed_vote_body_is_a_clean_400(self):
        self.create()
        url = f'/api/v1/polls/{self.poll().slug}/vote/'
        bodies = [json.dumps(body) for body in
                  ([1], "5", {'option': True}, {'option': 'abc'}, {}, {'option': 1.5},
                   {'option': -3}, {'option': '²'})]
        # json.dumps cheksizlikni «Infinity» deb yozadi — bu yerda xom matn kerak
        bodies.append('{"option": 1e400}')
        for body in bodies:
            response = self.client.post(url, body, content_type='application/json',
                                        **auth(self.users[0]))
            self.assertEqual(response.status_code, 400, body)
        self.assertFalse(PollVote.objects.exists())

    def test_vote_response_includes_own_vote_and_refreshes_cache(self):
        from django.core.cache import cache
        from django.test import override_settings as settings_override
        with settings_override(CACHES={'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}):
            cache.clear()
            self.create()
            slug = self.poll().slug
            vali = self.option("Aliyev Vali")
            before = self.client.get(f'/api/v1/polls/{slug}/').json()
            self.assertEqual(before['total_votes'], 0)

            data = self.vote(self.users[0], vali).json()
            self.assertEqual(data['total_votes'], 1)
            # Ovoz keshni o'chirmaydi — yangi holatni o'zi yozib qo'yadi
            self.assertEqual(cache.get(f'poll:public:{slug}')['total_votes'], 1)
            # Keyingi ko'ruvchi eski (0 ovozli) nusxani emas, yangisini oladi
            after = self.client.get(f'/api/v1/polls/{slug}/').json()
            self.assertEqual(after['total_votes'], 1)
            cache.clear()

    def test_option_from_another_poll_is_rejected(self):
        self.create()
        other = Poll.objects.create(title="Boshqa so'rovnoma")
        stranger = PollOption.objects.create(poll=other, name="Begona")
        response = self.vote(self.users[0], stranger)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PollVote.objects.exists())

    def test_closed_poll_takes_no_votes(self):
        self.create(ends_at=(timezone.now() - timedelta(hours=1)).isoformat())
        response = self.vote(self.users[0], self.option("Aliyev Vali"))
        self.assertEqual(response.status_code, 400)
        detail = self.client.get(f'/api/v1/polls/{self.poll().slug}/').json()
        self.assertTrue(detail['is_closed'])
        self.assertFalse(detail['is_open'])

    def test_hidden_results_show_no_counts(self):
        self.create(show_results='false')
        self.vote(self.users[0], self.option("Rasulov Sardor"))
        data = self.client.get(f'/api/v1/polls/{self.poll().slug}/').json()

        self.assertIsNone(data['total_votes'])
        self.assertNotIn('votes', data['options'][0])
        # Tartib — panelda kiritilgandek, ovozga qarab emas
        self.assertEqual(data['options'][0]['name'], "Aliyev Vali")

    def test_public_list_shows_top_three(self):
        self.create(options=[{'name': f"Nomzod {n}"} for n in range(5)])
        Poll.objects.create(title="Yashirin so'rovnoma", is_active=False)
        self.vote(self.users[0], self.option("Nomzod 4"))

        data = self.client.get('/api/v1/polls/').json()
        self.assertEqual(data['count'], 1)
        row = data['results'][0]
        self.assertEqual(row['options_count'], 5)
        self.assertEqual(len(row['options']), 3)
        self.assertEqual(row['options'][0]['name'], "Nomzod 4")

    def test_podium_threshold_is_saved_and_published(self):
        self.create()
        data = self.client.get(f'/api/v1/polls/{self.poll().slug}/').json()
        # Standart — 1000 ovoz: undan kam ovozli nomzod 1-2-3 o'ringa chiqmaydi
        self.assertEqual(data['podium_min_votes'], 1000)

        response = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/',
                                     {'podium_min_votes': 50}, content_type='application/json',
                                     **auth(self.admin))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['podium_min_votes'], 50)
        self.assertEqual(PollOption.objects.count(), 3)

        bad = self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/',
                                {'podium_min_votes': -1}, content_type='application/json',
                                **auth(self.admin))
        self.assertEqual(bad.status_code, 400)

    # -- natijalar --------------------------------------------------------------

    def test_results_page_for_admin(self):
        self.create()
        vali = self.option("Aliyev Vali")
        self.vote(self.users[0], vali)
        self.vote(self.users[1], vali)
        self.vote(self.users[2], self.option("Karimova Zuhra"))

        url = f'/api/v1/panel/polls/{self.poll().pk}/natijalar/'
        data = self.client.get(url, **auth(self.admin)).json()
        self.assertEqual(data['total_votes'], 3)
        self.assertEqual(data['districts'], [{'district': 'urgut', 'label': "Urgut tumani",
                                              'votes': 3}])
        self.assertEqual(sum(day['votes'] for day in data['daily']), 3)
        self.assertEqual(data['voters_count'], 3)

        only = self.client.get(f'{url}?option={vali.pk}', **auth(self.admin)).json()
        self.assertEqual(only['voters_count'], 2)
        self.assertEqual({v['option'] for v in only['voters']}, {"Aliyev Vali"})

        self.assertEqual(self.client.get(url, **auth(self.users[0])).status_code, 404)

    # -- bot ------------------------------------------------------------------

    def test_bot_gets_the_poll_once_it_has_candidates(self):
        setting = BotSetting.load()
        setting.auto_post = True
        setting.save()

        self.create()
        posts = BotPost.objects.filter(kind=BotPost.Kind.POLL)
        self.assertEqual(posts.count(), 1)
        self.assertTrue(posts.get().link.endswith(f'/sorovnomalar/{self.poll().slug}'))

        # Tahrirlash qayta yubormaydi
        self.client.patch(f'/api/v1/panel/polls/{self.poll().pk}/', {'title': "Yangi sarlavha"},
                          content_type='application/json', **auth(self.admin))
        self.assertEqual(posts.count(), 1)

    def test_poll_added_in_django_admin_reaches_bot(self):
        setting = BotSetting.load()
        setting.auto_post = True
        setting.save()
        self.client.force_login(self.admin)
        response = self.client.post('/boshqaruv/content/poll/add/', {
            'title': "Admin so'rovnomasi", 'description': '', 'ends_at_0': '', 'ends_at_1': '',
            'is_active': 'on', 'show_results': 'on', 'podium_min_votes': '1000',
            'options-TOTAL_FORMS': '2', 'options-INITIAL_FORMS': '0',
            'options-MIN_NUM_FORMS': '0', 'options-MAX_NUM_FORMS': '1000',
            'options-0-order': '0', 'options-0-name': "Bir", 'options-0-mahalla': '',
            'options-0-district': '',
            'options-1-order': '1', 'options-1-name': "Ikki", 'options-1-mahalla': '',
            'options-1-district': '',
        })
        self.assertEqual(response.status_code, 302, response.content[:500])
        self.assertEqual(BotPost.objects.filter(kind=BotPost.Kind.POLL).count(), 1)

    def test_saving_many_candidates_checks_bot_once(self):
        from unittest import mock
        from apps.accounts import bot_feed
        options = [{'name': f"Nomzod {n}"} for n in range(40)]
        with mock.patch.object(bot_feed, '_poll_ready', wraps=bot_feed._poll_ready) as ready:
            self.create(options=options)
        # Poll saqlanganda bir marta + nomzodlardan keyin bir marta — har nomzod uchun emas
        self.assertLessEqual(ready.call_count, 2)

    def test_hidden_poll_is_not_sent_to_bot(self):
        setting = BotSetting.load()
        setting.auto_post = True
        setting.save()
        self.create(is_active='false')
        self.assertFalse(BotPost.objects.filter(kind=BotPost.Kind.POLL).exists())
