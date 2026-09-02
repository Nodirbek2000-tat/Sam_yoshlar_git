from django.test import TestCase, override_settings


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    """Maxsus xato sahifalari to'g'ri chiziladi."""

    def test_404_page(self):
        response = self.client.get('/bunday-sahifa-yoq/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, "Bu sahifa topilmadi", status_code=404)
        self.assertContains(response, "Bosh sahifaga", status_code=404)

    def test_404_does_not_leak_panel(self):
        """Panel havolasi terilganda ham 404 sahifa chiqadi, ma'lumot ko'rinmaydi."""
        response = self.client.get('/nazorat/foydalanuvchilar/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Bu sahifa topilmadi", status_code=404)


class HomePageTests(TestCase):
    def test_home_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sam-yosh tadbirkor.uz")

    def test_about_renders(self):
        response = self.client.get('/kengash-haqida/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kengash Haqida")
