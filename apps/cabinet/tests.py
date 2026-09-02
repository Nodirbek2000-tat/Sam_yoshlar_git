from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.business.models import BusinessProfile, Product

from .models import Appeal, Notification, Suggestion

User = get_user_model()


class CabinetPagesTests(TestCase):
    """Kabinetning barcha bo'limlari ochilishini tekshiradi."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='kabinet@example.com', password='Samyosh2026!', full_name="Kabinet Test",
        )
        self.client.force_login(self.user)

    def test_all_sections_render(self):
        names = ['dashboard', 'profile', 'business', 'appeals', 'suggestions', 'events',
                 'notifications']
        for name in names:
            with self.subTest(section=name):
                response = self.client.get(reverse(f'cabinet:{name}'))
                self.assertEqual(response.status_code, 200, name)

    def test_product_sections_require_business(self):
        """Biznes profil bo'lmasa, mahsulot/galereya/hujjat sahifalari biznesga yo'naltiradi."""
        for name in ['products', 'gallery', 'documents']:
            response = self.client.get(reverse(f'cabinet:{name}'))
            self.assertRedirects(response, reverse('cabinet:business'))

    def test_product_flow_with_business(self):
        BusinessProfile.objects.create(user=self.user, name="Test MChJ", sphere='it')

        response = self.client.get(reverse('cabinet:products'))
        self.assertEqual(response.status_code, 200)

        self.client.post(reverse('cabinet:products'), {
            'name': "Veb-sayt yaratish", 'description': "Korporativ saytlar",
            'price': '5000000', 'unit': 'dona', 'is_active': 'on',
        })
        product = Product.objects.get(name="Veb-sayt yaratish")
        self.assertEqual(product.business.user, self.user)

        self.client.post(reverse('cabinet:product_delete', kwargs={'pk': product.pk}))
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_appeal_submission(self):
        response = self.client.post(reverse('cabinet:appeals'), {
            'subject': "Grant bo'yicha savol", 'category': 'moliya',
            'message': "Grant arizasini qanday topshiraman?",
        })
        self.assertRedirects(response, reverse('cabinet:appeals'))
        appeal = Appeal.objects.get(user=self.user)
        self.assertEqual(appeal.status, 'pending')

    def test_suggestion_submission(self):
        self.client.post(reverse('cabinet:suggestions'), {
            'title': "Mobil ilova kerak", 'description': "Platforma uchun mobil ilova qiling.",
        })
        self.assertEqual(Suggestion.objects.filter(user=self.user).count(), 1)

    def test_notifications_mark_all_read(self):
        Notification.objects.create(user=self.user, title="Yangi grant")
        Notification.objects.create(user=self.user, title="Tadbir eslatmasi")

        response = self.client.get(reverse('cabinet:notifications'))
        self.assertContains(response, "Yangi grant")

        self.client.post(reverse('cabinet:notifications_read_all'))
        self.assertEqual(self.user.notifications.filter(is_read=False).count(), 0)

    def test_other_user_cannot_delete_product(self):
        business = BusinessProfile.objects.create(user=self.user, name="Meniki", sphere='it')
        product = Product.objects.create(business=business, name="Mahsulot")

        intruder = User.objects.create_user(email='begona@example.com', password='Samyosh2026!',
                                            full_name="Begona")
        self.client.force_login(intruder)
        response = self.client.post(reverse('cabinet:product_delete', kwargs={'pk': product.pk}))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
