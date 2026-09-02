import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.initiatives.models import Initiative, InitiativeComment

User = get_user_model()


class PanelImportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@samyosh.uz', password='Samyosh2026!', full_name="Admin",
        )
        self.client.force_login(self.admin)
        self.url = reverse('panel:import')

    def _payload(self, **overrides):
        item = {
            'direction': 'eco',
            'kind': 'idea',
            'title': "Import qilingan g'oya",
            'description': "Tavsif matni.",
            'author_name': "Aziz Rahimov",
            'region': 'samarqand',
            'vote_count': 42,
            'created_at': '2026-08-15',
            'comments': [
                {'author_name': "Nodira", 'text': "Zo'r!", 'created_at': '2026-08-16'},
                {'author_name': "Bobur", 'text': "Qo'llab-quvvatlayman"},
            ],
        }
        item.update(overrides)
        return json.dumps({'initiatives': [item]}, ensure_ascii=False)

    def test_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "JSON import")

    def test_import_creates_everything(self):
        self.client.post(self.url, {'data': self._payload(), 'mode': 'add'})

        idea = Initiative.objects.get(title="Import qilingan g'oya")
        self.assertEqual(idea.vote_count, 42)
        self.assertEqual(idea.direction, 'eco')
        self.assertEqual(idea.author_name, "Aziz Rahimov")
        self.assertEqual(idea.comments.count(), 2)
        self.assertEqual(idea.created_at.year, 2026)
        self.assertEqual(idea.created_at.month, 8)

    def test_plain_list_accepted(self):
        raw = json.dumps([{'direction': 'ai', 'title': "Ro'yxat", 'description': "X"}])
        self.client.post(self.url, {'data': raw, 'mode': 'add'})
        self.assertTrue(Initiative.objects.filter(title="Ro'yxat").exists())

    def test_bad_json_reported(self):
        response = self.client.post(self.url, {'data': '{ buzuq', 'mode': 'add'})
        self.assertContains(response, "JSON xato")
        self.assertEqual(Initiative.objects.count(), 0)

    def test_unknown_direction_skipped(self):
        response = self.client.post(self.url,
                                    {'data': self._payload(direction='yoq'), 'mode': 'add'})
        self.assertContains(response, "noma&#x27;lum yo&#x27;nalish")
        self.assertEqual(Initiative.objects.count(), 0)

    def test_missing_title_skipped(self):
        self.client.post(self.url, {'data': self._payload(title=''), 'mode': 'add'})
        self.assertEqual(Initiative.objects.count(), 0)

    def test_replace_mode_clears_first(self):
        Initiative.objects.create(direction='eco', kind='idea', title="Eski",
                                  description="X", author_name="A")

        self.client.post(self.url, {'data': self._payload(), 'mode': 'replace'})

        self.assertFalse(Initiative.objects.filter(title="Eski").exists())
        self.assertEqual(Initiative.objects.count(), 1)

    def test_add_mode_keeps_existing(self):
        Initiative.objects.create(direction='eco', kind='idea', title="Eski",
                                  description="X", author_name="A")

        self.client.post(self.url, {'data': self._payload(), 'mode': 'add'})
        self.assertEqual(Initiative.objects.count(), 2)

    def test_export_returns_json(self):
        self.client.post(self.url, {'data': self._payload(), 'mode': 'add'})

        response = self.client.get(reverse('panel:export'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

        data = json.loads(response.content)
        self.assertEqual(len(data['initiatives']), 1)
        self.assertEqual(data['initiatives'][0]['vote_count'], 42)
        self.assertEqual(len(data['initiatives'][0]['comments']), 2)

    def test_export_import_roundtrip(self):
        self.client.post(self.url, {'data': self._payload(), 'mode': 'add'})
        exported = self.client.get(reverse('panel:export')).content.decode()

        self.client.post(self.url, {'data': exported, 'mode': 'replace'})

        self.assertEqual(Initiative.objects.count(), 1)
        self.assertEqual(InitiativeComment.objects.count(), 2)
        self.assertEqual(Initiative.objects.first().vote_count, 42)

    def test_outsider_blocked(self):
        outsider = User.objects.create_user(email='begona@example.com',
                                            password='Samyosh2026!', full_name="Begona")
        self.client.force_login(outsider)

        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.get(reverse('panel:export')).status_code, 404)
