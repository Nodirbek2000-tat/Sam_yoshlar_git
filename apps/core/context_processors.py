from django.db import DatabaseError

from .models import SiteSetting


def site_settings(request):
    """Har bir sahifada footer/header ma'lumotlari va o'qilmagan bildirishnomalar soni."""
    try:
        settings_obj = SiteSetting.load()
    except DatabaseError:
        settings_obj = None

    unread = 0
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        try:
            unread = user.notifications.filter(is_read=False).count()
        except DatabaseError:
            unread = 0

    return {'site': settings_obj, 'unread_count': unread}
