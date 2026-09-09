from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from apps.core.constants import Status

from .directions import DIRECTIONS
from .models import Initiative, InitiativeVote

User = get_user_model()


class VoicePageTests(TestCase):
    def setUp(self):
        self.idea = Initiative.objects.create(
            direction='eco', kind='idea', title="Maktabda plastik yig'ish",
            description="Har bir maktabda yig'ish punkti.", author_name="Aziz",
            vote_count=5,
        )

    def test_page_renders_all_directions(self):
        response = self.client.get(reverse('initiatives:youth'))
        self.assertEqual(response.status_code, 200)
        for item in DIRECTIONS:
            self.assertContains(response, escape(item['name']))

    def test_direction_page_shows_own_ideas(self):
        other = Initiative.objects.create(
            direction='ai', kind='idea', title="Nutq korpusi",
            description="Ochiq audio baza.", author_name="Bobur",
        )
        response = self.client.get(reverse('initiatives:youth_direction',
                                           kwargs={'direction_id': 'eco'}))
        self.assertContains(response, "Maktabda plastik")
        self.assertNotContains(response, other.title)

    def test_ranking_order(self):
        top = Initiative.objects.create(
            direction='eco', kind='idea', title="Eng zo'r g'oya",
            description="X", author_name="Nilufar", vote_count=99,
        )
        response = self.client.get(reverse('initiatives:youth_direction',
                                           kwargs={'direction_id': 'eco'}))
        ideas = response.context['ranking']
        self.assertEqual(ideas[0], top)
        self.assertEqual(ideas[1], self.idea)

    def test_unknown_direction_falls_back(self):
        response = self.client.get(reverse('initiatives:youth_direction',
                                           kwargs={'direction_id': 'bunday-yoq'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active']['id'], DIRECTIONS[0]['id'])


class VoteTests(TestCase):
    def setUp(self):
        self.idea = Initiative.objects.create(
            direction='eco', kind='idea', title="G'oya", description="X",
            author_name="Aziz", vote_count=3,
        )
        self.url = reverse('initiatives:vote', kwargs={'pk': self.idea.pk})

    def _login(self, email='ovoz@example.com'):
        user = User.objects.create_user(email=email, password='Samyosh2026!', full_name="Ovoz")
        self.client.force_login(user)
        return user

    def test_guest_cannot_vote(self):
        """Ovoz berish faqat ro'yxatdan o'tganlar uchun."""
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertEqual(data['reason'], 'auth')
        self.assertIn(reverse('accounts:login'), data['login_url'])

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 3)
        self.assertEqual(InitiativeVote.objects.count(), 0)

    def test_logged_in_can_vote_once(self):
        self._login()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['votes'], 4)

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 4)

    def test_second_vote_rejected(self):
        self._login()
        self.client.post(self.url)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['ok'])
        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 4)

    def test_user_vote_once(self):
        user = User.objects.create_user(email='ovoz@example.com', password='Samyosh2026!',
                                        full_name="Ovoz Beruvchi")
        self.client.force_login(user)

        self.assertTrue(self.client.post(self.url).json()['ok'])
        self.assertEqual(self.client.post(self.url).status_code, 409)
        self.assertEqual(InitiativeVote.objects.filter(user=user).count(), 1)

    def test_different_users_both_vote(self):
        for email in ['a@b.uz', 'c@d.uz']:
            user = User.objects.create_user(email=email, password='Samyosh2026!', full_name="X")
            self.client.force_login(user)
            self.client.post(self.url)

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.vote_count, 5)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_hidden_initiative_cannot_be_voted(self):
        self.idea.is_published = False
        self.idea.save()
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_milestone_message(self):
        self._login()
        self.idea.vote_count = 4
        self.idea.save()
        data = self.client.post(self.url).json()
        self.assertTrue(data['milestone'])
        self.assertIn('5 ta ovoz', data['message'])


class InitiativeCreateTests(TestCase):
    def _data(self, **overrides):
        data = {
            'direction': 'ai', 'kind': 'startup',
            'title': "O'zbek tili uchun ochiq korpus",
            'summary': "Ovozli yordamchi uchun baza",
            'description': "Ochiq audio-matn bazasi yaratish kerak.",
            'author_name': "Madina Yusupova",
        }
        data.update(overrides)
        return data

    def test_form_renders(self):
        response = self.client.get(reverse('initiatives:initiative_create_direction',
                                           kwargs={'direction_id': 'ai'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tashabbus bildirish")

    def test_create(self):
        response = self.client.post(reverse('initiatives:initiative_create'), self._data())
        self.assertEqual(response.status_code, 302)

        initiative = Initiative.objects.get(title="O'zbek tili uchun ochiq korpus")
        self.assertEqual(initiative.direction, 'ai')
        self.assertEqual(initiative.vote_count, 0)
        self.assertEqual(initiative.status, Status.APPROVED)

    def test_author_linked_when_logged_in(self):
        user = User.objects.create_user(email='muallif@example.com', password='Samyosh2026!',
                                        full_name="Muallif")
        self.client.force_login(user)
        self.client.post(reverse('initiatives:initiative_create'), self._data())

        self.assertEqual(Initiative.objects.first().author, user)

    def test_required_fields(self):
        response = self.client.post(reverse('initiatives:initiative_create'),
                                    self._data(title='', description=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Initiative.objects.count(), 0)

    def test_new_idea_appears_in_ranking(self):
        self.client.post(reverse('initiatives:initiative_create'), self._data())
        response = self.client.get(reverse('initiatives:youth_direction',
                                           kwargs={'direction_id': 'ai'}))
        self.assertContains(response, escape("O'zbek tili uchun ochiq korpus"))


class CommentTests(TestCase):
    """Taklif berish (izoh) va muallifga bildirishnoma."""

    def setUp(self):
        self.author = User.objects.create_user(email='muallif@example.com',
                                               password='Samyosh2026!', full_name="Muallif")
        self.idea = Initiative.objects.create(
            direction='eco', kind='problem', title="Chiqindi muammosi",
            description="Mahallada chiqindi yig'ilmayapti.", author=self.author,
            author_name="Muallif",
        )
        self.url = reverse('initiatives:initiative_detail', kwargs={'pk': self.idea.pk})

    def test_detail_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chiqindi muammosi")
        self.assertContains(response, "Takliflar")

    def _login_youth(self):
        youth = User.objects.create_user(email='yosh@example.com', password='Samyosh2026!',
                                         full_name="Yosh Dasturchi")
        self.client.force_login(youth)
        return youth

    def test_guest_sees_login_invite(self):
        """Mehmon o'qiy oladi, lekin taklif bera olmaydi."""
        response = self.client.get(self.url)
        self.assertContains(response, "Taklif berish uchun ro")
        self.assertNotContains(response, 'class="voice-comment-form"')

    def test_guest_cannot_comment(self):
        response = self.client.post(self.url, {
            'author_name': "Yosh Dasturchi",
            'text': "Telegram bot orqali chaqiruv tizimi qilish mumkin.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])
        self.assertEqual(self.idea.comments.count(), 0)

    def test_logged_in_can_comment(self):
        self._login_youth()
        response = self.client.post(self.url, {
            'author_name': "Yosh Dasturchi",
            'text': "Telegram bot orqali chaqiruv tizimi qilish mumkin.",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.idea.comments.count(), 1)

    def test_comment_notifies_author(self):
        self._login_youth()
        self.client.post(self.url, {'author_name': "Yosh", 'text': "Taklif matni"})
        self.assertEqual(self.author.notifications.count(), 1)
        self.assertIn("yangi taklif", self.author.notifications.first().title.lower())

    def test_own_comment_does_not_notify(self):
        self.client.force_login(self.author)
        self.client.post(self.url, {'author_name': "Muallif", 'text': "O'zim yozdim"})
        self.assertEqual(self.author.notifications.count(), 0)

    def test_empty_comment_rejected(self):
        self._login_youth()
        response = self.client.post(self.url, {'author_name': "Yosh", 'text': ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.idea.comments.count(), 0)

    def test_comment_visible_on_page(self):
        self._login_youth()
        self.client.post(self.url, {'author_name': "Yosh Dasturchi", 'text': "Bot qilaylik"})
        response = self.client.get(self.url)
        self.assertContains(response, "Bot qilaylik")


class MilestoneNotificationTests(TestCase):
    def test_author_notified_on_milestone(self):
        author = User.objects.create_user(email='a@b.uz', password='Samyosh2026!', full_name="A")
        idea = Initiative.objects.create(
            direction='eco', kind='idea', title="G'oya", description="X",
            author=author, author_name="A", vote_count=4,
        )
        voter = User.objects.create_user(email='ovoz@b.uz', password='Samyosh2026!', full_name="V")
        self.client.force_login(voter)
        self.client.post(reverse('initiatives:vote', kwargs={'pk': idea.pk}))
        self.assertEqual(author.notifications.count(), 1)
        self.assertIn("5 ta ovoz", author.notifications.first().title)


class MyInitiativesTests(TestCase):
    """Kabinetdagi «Tashabbuslarim»."""

    def setUp(self):
        self.user = User.objects.create_user(email='men@example.com', password='Samyosh2026!',
                                             full_name="Men")
        self.mine = Initiative.objects.create(
            direction='eco', kind='idea', title="Mening g'oyam", description="X",
            author=self.user, author_name="Men", vote_count=7,
        )
        Initiative.objects.create(
            direction='eco', kind='idea', title="Begona g'oya", description="Y",
            author_name="Begona", vote_count=99,
        )
        self.client.force_login(self.user)

    def test_only_own_initiatives_listed(self):
        response = self.client.get(reverse('cabinet:initiatives'))
        self.assertContains(response, "Mening g")
        self.assertNotContains(response, "Begona g")

    def test_rank_shown(self):
        response = self.client.get(reverse('cabinet:initiatives'))
        self.assertEqual(response.context['initiatives'][0].place, 2)

    def test_author_can_delete(self):
        response = self.client.post(
            reverse('initiatives:initiative_delete', kwargs={'pk': self.mine.pk})
        )
        self.assertRedirects(response, reverse('cabinet:initiatives'))
        self.assertFalse(Initiative.objects.filter(pk=self.mine.pk).exists())

    def test_cannot_delete_others(self):
        other = Initiative.objects.get(title="Begona g'oya")
        response = self.client.post(
            reverse('initiatives:initiative_delete', kwargs={'pk': other.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Initiative.objects.filter(pk=other.pk).exists())

    def test_anonymous_redirected(self):
        self.client.logout()
        response = self.client.post(
            reverse('initiatives:initiative_delete', kwargs={'pk': self.mine.pk})
        )
        self.assertEqual(response.status_code, 302)
