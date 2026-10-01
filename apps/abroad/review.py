"""Chet eldagi tengdosh anketasi: tekshiruvga tushdi va natija xabarlari.

Yangi anketa avval «kutilmoqda» holatida turadi — saytda ham, botda ham
ko'rinmaydi. Panel adminlari Telegram'da xabar oladi. Admin tasdiqlasa,
anketa saytga chiqadi, bot obunachilarga yuboradi (`bot_feed`) va egasiga
«tasdiqlandi» degan xabar boradi.
"""

from html import escape

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounts.bot_messages import send_personal
from apps.cabinet.models import Notification
from apps.core.constants import Status

PANEL_LINK = '/nazorat/tengdoshlar'
CABINET_LINK = '/kabinet/tengdosh'


def panel_admins():
    """Telegram'i ulangan panel adminlari."""
    return (get_user_model().objects
            .filter(is_active=True, telegram_id__gt=0)
            .filter(Q(is_superuser=True) | Q(is_staff=True, is_verified=True, role='admin')))


def notify_admins(peer):
    """Yangi (yoki tuzatilgan) anketa tekshiruvni kutmoqda."""
    text = "\n".join([
        "🌍 <b>Yangi tengdosh anketasi tekshiruvni kutmoqda</b>",
        "",
        f"👤 {escape(peer.full_name)}",
        f"📍 {escape(peer.city + ', ' if peer.city else '')}{escape(peer.get_country_display())}",
        f"🎓 {escape(peer.institution or '—')}",
    ])
    for admin in panel_admins():
        send_personal(admin, text, [{'text': "🛠 Panelda ko'rish", 'url': PANEL_LINK}])


def notify_owner(peer):
    """Admin qaroridan keyin — anketa egasiga saytda va botda xabar."""
    owner = peer.user
    if not owner:
        return

    if peer.status == Status.APPROVED:
        Notification.objects.create(
            user=owner, title="Anketangiz tasdiqlandi",
            message="Endi siz «Chet eldagi tengdoshlar» ro'yxatida ko'rinasiz.",
            type='success', link=f'/tengdoshlar/{peer.pk}')
        send_personal(owner, "\n".join([
            "✅ <b>Anketangiz tasdiqlandi!</b>",
            "",
            "Endi siz saytdagi «Chet eldagi tengdoshlar» ro'yxatida ko'rinasiz — "
            "yurtdoshlaringiz siz bilan bog'lana oladi.",
        ]), [{'text': "🌍 Profilimni ko'rish", 'url': f'/tengdoshlar/{peer.pk}'}])
    elif peer.status == Status.REJECTED:
        note = f" Izoh: {peer.admin_note}" if peer.admin_note else ""
        Notification.objects.create(
            user=owner, title="Anketangiz qaytarildi",
            message=f"Ma'lumotlarni tuzatib qayta saqlang — anketa yana ko'rib chiqiladi.{note}",
            type='warning', link=CABINET_LINK)
        send_personal(owner, "\n".join([
            "↩️ <b>Anketangiz qaytarildi</b>",
            "",
            "Ma'lumotlarni tuzatib qayta saqlang — anketa yana ko'rib chiqiladi."
            + (f"\n\nIzoh: {escape(peer.admin_note)}" if peer.admin_note else ""),
        ]), [{'text': "✏️ Anketani tuzatish", 'url': CABINET_LINK}])
