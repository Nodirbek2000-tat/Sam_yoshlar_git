"""Ro'yxatdan o'tish qadamlari.

Telegram orqali kelgan foydalanuvchi uch holatdan birida bo'ladi:

    'role'      — hali kim ekanini tanlamagan
    'business'  — tadbirkor, lekin biznes ma'lumotini bermagan
    'startup'   — startupper, lekin startapini kiritmagan
    None        — hammasi to'ldirilgan

Front shu qiymatga qarab foydalanuvchini kerakli sahifaga yuboradi —
kirishda ham, kabinetni ochganda ham. Shuning uchun biror qadamni
«keyinroq» deb tashlab ketib bo'lmaydi.
"""

from apps.accounts.models import Role
from apps.business.models import BusinessProfile
from apps.startups.models import Startup

#: Tashkilot va admin hisobini biz o'zimiz ochamiz — ulardan so'ralmaydi
EXEMPT_ROLES = {Role.ADMIN, Role.ORGANIZATION}


def onboarding_step(user):
    """Qaysi qadam qolganini qaytaradi; hammasi tayyor bo'lsa — `None`."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser or user.role in EXEMPT_ROLES:
        return None
    if not user.is_verified:
        return 'role'
    if user.role == Role.ENTREPRENEUR:
        business = BusinessProfile.objects.filter(user=user).first()
        # Logotip va kamida bitta rasm — ro'yxatda bo'sh karta chiqmasin
        if business is None or not business.logo or not business.gallery.exists():
            return 'business'
    if user.role == Role.STARTUPPER:
        startup = Startup.objects.filter(user=user).first()
        if startup is None or not startup.logo:
            return 'startup'
    return None
