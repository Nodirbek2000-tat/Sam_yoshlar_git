from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.constants import Status

from .models import Peer

User = get_user_model()


class PeerListTests(TestCase):
    def setUp(self):
        self.approved = Peer.objects.create(
            full_name="Jasur Abdullayev", country='germany', city="Berlin",
            purpose='study', institution="TU Berlin", about="Magistraturada o'qiyman.",
            telegram="@jasur", status=Status.APPROVED,
        )
        self.pending = Peer.objects.create(
            full_name="Kutayotgan Anketa", country='usa', purpose='work',
            about="Hali tasdiqlanmagan.", email="x@y.uz", status=Status.PENDING,
        )

    def test_only_approved_listed(self):
        response = self.client.get(reverse('abroad:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jasur Abdullayev")
        self.assertNotContains(response, "Kutayotgan Anketa")

    def test_filter_by_country(self):
        Peer.objects.create(full_name="Koreyalik Yurtdosh", country='korea', purpose='work',
                            about="X", telegram="@k", status=Status.APPROVED)

        response = self.client.get(reverse('abroad:list'), {'davlat': 'germany'})
        self.assertContains(response, "Jasur Abdullayev")
        self.assertNotContains(response, "Koreyalik Yurtdosh")

    def test_search(self):
        response = self.client.get(reverse('abroad:list'), {'q': 'Berlin'})
        self.assertContains(response, "Jasur Abdullayev")

    def test_detail_shows_contacts(self):
        response = self.client.get(self.approved.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TU Berlin")
        self.assertContains(response, "@jasur")

    def test_pending_detail_is_404(self):
        response = self.client.get(reverse('abroad:detail', kwargs={'pk': self.pending.pk}))
        self.assertEqual(response.status_code, 404)

    def test_menu_link_present(self):
        response = self.client.get('/')
        self.assertContains(response, "Chet eldagi tengdoshim")
        self.assertContains(response, '/chet-eldagi-tengdoshim/')


class PeerJoinTests(TestCase):
    def _data(self, **overrides):
        data = {
            'full_name': "Yangi Yurtdosh",
            'country': 'turkey',
            'city': "Istanbul",
            'purpose': 'study',
            'about': "Istanbulda o'qiyman.",
            'telegram': "@yangi",
        }
        data.update(overrides)
        return data

    def test_form_renders(self):
        response = self.client.get(reverse('abroad:join'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Men ham chet eldaman")

    def test_join_creates_pending_peer(self):
        response = self.client.post(reverse('abroad:join'), self._data())
        self.assertRedirects(response, reverse('abroad:list'))

        peer = Peer.objects.get(full_name="Yangi Yurtdosh")
        self.assertEqual(peer.status, Status.PENDING)

        # Tasdiqlanmaguncha ro'yxatda ko'rinmaydi
        self.assertNotContains(self.client.get(reverse('abroad:list')), "Yangi Yurtdosh")

    def test_contact_required(self):
        response = self.client.post(reverse('abroad:join'),
                                    self._data(telegram='', email='', phone='', instagram=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Peer.objects.count(), 0)
        self.assertContains(response, "Kamida bitta aloqa usulini")

    def test_required_fields(self):
        response = self.client.post(reverse('abroad:join'), self._data(full_name='', about=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Peer.objects.count(), 0)

    def test_author_linked_when_logged_in(self):
        user = User.objects.create_user(email='men@example.com', password='Samyosh2026!',
                                        full_name="Men")
        self.client.force_login(user)
        self.client.post(reverse('abroad:join'), self._data())

        self.assertEqual(Peer.objects.first().user, user)


class PeerPanelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@samyosh.uz',
                                                   password='Samyosh2026!', full_name="Admin")
        self.peer = Peer.objects.create(full_name="Tekshiriluvchi", country='usa',
                                        purpose='study', about="X", telegram="@t")

    def test_outsider_gets_404(self):
        response = self.client.get(reverse('panel:peers'))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("Tekshiriluvchi", response.content.decode())

    def test_admin_sees_list(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('panel:peers'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tekshiriluvchi")

    def test_approve_publishes_and_notifies(self):
        person = User.objects.create_user(email='p@example.com', password='Samyosh2026!',
                                          full_name="Ariza Beruvchi")
        self.peer.user = person
        self.peer.save()

        self.client.force_login(self.admin)
        response = self.client.post(reverse('panel:peer_status', kwargs={'pk': self.peer.pk}),
                                    {'status': Status.APPROVED})
        self.assertRedirects(response, reverse('panel:peers'))

        self.peer.refresh_from_db()
        self.assertEqual(self.peer.status, Status.APPROVED)
        self.assertEqual(person.notifications.count(), 1)

        # Endi saytda ko'rinadi
        self.client.logout()
        self.assertContains(self.client.get(reverse('abroad:list')), "Tekshiriluvchi")
