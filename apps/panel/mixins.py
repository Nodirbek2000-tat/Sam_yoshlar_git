"""Panelga kirishni cheklash.

Muhim: ruxsati yo'q foydalanuvchiga 403 emas, **404** qaytariladi — shunda panel
umuman mavjudligi bilinmaydi va havolani qo'lda tersa ham hech narsa ko'rinmaydi.
"""

from functools import wraps

from django.http import Http404


def is_panel_admin(user):
    """Panelga faqat tasdiqlangan admin/xodim kira oladi."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.is_staff and user.is_verified and user.role == 'admin'


def panel_required(view_func):
    """Funksiya-view uchun dekorator."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_panel_admin(request.user):
            raise Http404
        return view_func(request, *args, **kwargs)

    return wrapper


class PanelAccessMixin:
    """Class-based view'lar uchun."""

    def dispatch(self, request, *args, **kwargs):
        if not is_panel_admin(request.user):
            raise Http404
        return super().dispatch(request, *args, **kwargs)
