"""Ikonka sprite'i har bir sahifada bor va barcha havolalar joyida ekanini tekshiradi.

Sprite `templates/partials/icons.html` da. Agar shablon uni `include` qilmasa
yoki mavjud bo'lmagan `#ic-...` ga murojaat qilsa — ikonka ko'rinmay qoladi,
lekin sahifa xatosiz ochilaveradi. Shuning uchun test kerak.
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()

PUBLIC_PAGES = [
    ('/', "bosh sahifa"),
    ('/yangiliklar/', "yangiliklar"),
    ('/tadbirlar/', "tadbirlar"),
    ('/elonlar/', "e'lonlar"),
    ('/tashabbuslar/', "tashabbuslar"),
    ('/tashabbuslar/yoshlar/', "reyting"),
    ('/tashabbuslar/muammolar/', "tashkilot muammolari"),
    ('/chet-eldagi-tengdoshim/', "chet eldagi tengdoshim"),
    ('/kirish/', "kirish"),
    ('/kengash-haqida/', "kengash haqida"),
]

USED = re.compile(r'<use href="#(ic-[\w-]+)"')
DEFINED = re.compile(r'<symbol id="(ic-[\w-]+)"')


class IconSpriteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@mentadbirkor.uz', password='Parol2026!', full_name="Admin")

    def assertIconsResolve(self, url, name):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, f"{name}: {response.status_code}")

        html = response.content.decode()
        self.assertIn('id="ic-home"', html, f"{name}: sprite qo'shilmagan")

        missing = set(USED.findall(html)) - set(DEFINED.findall(html))
        self.assertFalse(missing, f"{name}: sprite'da yo'q ikonkalar — {sorted(missing)}")

    def test_public_pages(self):
        for url, name in PUBLIC_PAGES:
            with self.subTest(page=name):
                self.assertIconsResolve(url, name)

    def test_cabinet_and_panel(self):
        self.client.force_login(self.admin)
        self.assertIconsResolve('/kabinet/', "kabinet")
        self.assertIconsResolve('/nazorat/', "boshqaruv paneli")
