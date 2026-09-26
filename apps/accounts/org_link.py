"""Tashkilot hisobini Telegram bilan bog'lash.

Tashkilotga login va parolni panelda biz beramiz. Birinchi kirishda sayt
darhol kiritmaydi — Telegram hisobini ulashni so'raydi (``TelegramLink``):

    sayt: login-parol       -> start_link()     -> ticket + bot havolasi
    bot:  /start org_<...>  -> open_link()      -> «raqamingizni yuboring»
    bot:  raqam             -> complete_link()  -> «Xush kelibsiz, <tashkilot>!»
    sayt: ticket            -> link_status()    -> ulandi: kirish tokeni

Ulangandan keyin tashkilot saytga login-parol bilan ham, botdagi kod bilan
ham kiraveradi. Tashkilot oddiy foydalanuvchi sifatida sanalmaydi va botda
undan yosh ham, tuman ham so'ralmaydi.
"""

import secrets

from django.conf import settings
from django.db import router, transaction
from django.db.models import ProtectedError, RestrictedError
from django.db.models.deletion import Collector
from django.utils import timezone

from .models import Role, TelegramAuthCode, TelegramLink, User

#: Bot havolasidagi belgi: ``/start org_<token>``
START_PREFIX = 'org_'


def needs_telegram(user):
    """Login-parol bilan kirgan tashkilotning Telegram'i hali ulanmaganmi."""
    return user.role == Role.ORGANIZATION and not user.telegram_id


def organization_name(user):
    """Botda va saytda ko'rinadigan nom — tashkilotning o'z nomi."""
    organization = user.organizations.order_by('created_at').first()
    return organization.name if organization else user.full_name


def bot_username():
    return getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or 'yoshtadbirkorlarbot'


def bot_url(link):
    return f"https://t.me/{bot_username()}?start={START_PREFIX}{link.token}"


# --------------------------------------------------------------------------
# 1. Sayt: havola ochish
# --------------------------------------------------------------------------

def start_link(user):
    """Yangi ulash havolasini ochadi. Tugallanmagan eskilari bekor bo'ladi."""
    TelegramLink.objects.filter(user=user, linked_at__isnull=True).delete()
    return TelegramLink.objects.create(
        user=user,
        token=secrets.token_urlsafe(24),
        ticket=secrets.token_urlsafe(32),
    )


def link_payload(link):
    """Saytga qaytadigan ma'lumot — bot havolasi va holatni so'rash kaliti."""
    return {
        'telegram_required': True,
        'ticket': link.ticket,
        'bot_url': bot_url(link),
        'organization': organization_name(link.user),
        'first_login': link.user.last_login is None,
        'expires_in': int(TelegramLink.LIFETIME.total_seconds()),
    }


# --------------------------------------------------------------------------
# 2–3. Bot: havolani ochish va raqam bilan ulash
# --------------------------------------------------------------------------

def parse_start(payload):
    """``org_<token>`` -> token (boshqa narsa bo'lsa — None)."""
    payload = (payload or '').strip()
    if not payload.startswith(START_PREFIX):
        return None
    return payload[len(START_PREFIX):] or None


def _result(error=None, link=None, **extra):
    data = {'ok': error is None}
    if error:
        data['error'] = error
    if link is not None:
        data['organization'] = organization_name(link.user)
    data.update(extra)
    return data


def _check(link, telegram_id):
    """Ulashga to'sqinlik bo'lsa — xato kodi, bo'lmasa None."""
    if link is None:
        return 'bad_link'

    owner = link.user
    if link.linked_at is not None:
        return 'already_linked' if owner.telegram_id == telegram_id else 'bad_link'
    if link.is_expired:
        return 'expired'
    if not owner.is_active or owner.role != Role.ORGANIZATION:
        return 'bad_link'
    if owner.telegram_id and owner.telegram_id != telegram_id:
        return 'org_taken'

    other = User.objects.filter(telegram_id=telegram_id).exclude(pk=owner.pk).first()
    if other is not None and not is_disposable_account(other):
        return 'telegram_taken'
    return None


def _locked_link(token):
    return (TelegramLink.objects.select_for_update().select_related('user')
            .filter(token=token).first())


def open_link(token, telegram_id):
    """Bot ``/start org_<token>`` oldi: tashkilotni taniymiz, raqam so'raladi."""
    with transaction.atomic():
        link = _locked_link(token)
        error = _check(link, telegram_id)

        if error == 'already_linked':
            return _result(link=link, already=True)
        if error:
            return _result(error, link=None if error == 'bad_link' else link)

        link.telegram_id = telegram_id
        link.opened_at = link.opened_at or timezone.now()
        link.save(update_fields=['telegram_id', 'opened_at'])

    return _result('need_phone', link=link)


def complete_link(token, telegram_id, phone, username=''):
    """Raqam keldi: Telegram tashkilot hisobiga ulanadi."""
    from .telegram_views import normalize_phone

    phone = normalize_phone(phone)

    with transaction.atomic():
        link = _locked_link(token)
        error = _check(link, telegram_id)

        if error == 'already_linked':
            return _result(link=link, already=True)
        if error:
            return _result(error, link=None if error == 'bad_link' else link)
        if not phone:
            return _result('need_phone', link=link)

        owner = User.objects.select_for_update().get(pk=link.user_id)

        # Shu Telegram bilan bot avval ochib qo'ygan bo'sh hisob bo'lsa —
        # u endi kerak emas, Telegram tashkilotga o'tadi
        # (_check uni bo'shligini allaqachon tekshirgan)
        other = User.objects.filter(telegram_id=telegram_id).exclude(pk=owner.pk).first()
        if other is not None:
            if other.avatar:
                other.avatar.delete(save=False)
            other.delete()

        owner.telegram_id = telegram_id
        owner.telegram_username = (username or '').strip().lstrip('@')
        owner.phone = phone
        owner.save(update_fields=['telegram_id', 'telegram_username', 'phone'])

        link.telegram_id = telegram_id
        link.linked_at = timezone.now()
        link.save(update_fields=['telegram_id', 'linked_at'])

    return _result(link=link)


# --------------------------------------------------------------------------
# 4. Sayt: holatni so'rash
# --------------------------------------------------------------------------

def link_status(ticket):
    """(holat, hisob) — holat ``linked`` bo'lsa hisob qaytadi va kalit yopiladi.

    Holatlar: ``waiting`` (bot hali ochilmagan), ``phone`` (bot ochildi,
    raqam kutilmoqda), ``linked``, ``expired``, ``used``, ``invalid``.
    """
    link = None
    if ticket:
        link = TelegramLink.objects.select_related('user').filter(ticket=ticket).first()

    if link is None:
        return 'invalid', None
    if link.claimed_at is not None:
        return 'used', None

    if link.linked_at is not None:
        if not link.can_claim:
            return 'expired', None
        # Ikki oyna bir vaqtda so'rasa ham token faqat bittasiga beriladi
        claimed = (TelegramLink.objects.filter(pk=link.pk, claimed_at__isnull=True)
                   .update(claimed_at=timezone.now()))
        return ('linked', link.user) if claimed else ('used', None)

    if link.is_expired:
        return 'expired', None
    return ('phone' if link.opened_at else 'waiting'), None


# --------------------------------------------------------------------------
# Yordamchi
# --------------------------------------------------------------------------

#: Bo'sh hisobni o'chirganda shular bilan birga ketishi zararsiz
_HARMLESS = {User, TelegramAuthCode, TelegramLink}


def is_disposable_account(user):
    """Bot o'zi ochgan, lekin hech narsa qilinmagan bo'sh hisobmi.

    Tashkilot xodimi avval botga oddiy odam sifatida kirib ko'rgan bo'lsa,
    uning Telegram'i o'sha bo'sh hisobga bog'lanib qolgan bo'ladi. Unda
    tashabbus, ovoz, izoh, anketa — hech narsa bo'lmasa, o'chirib yuborish
    xavfsiz. Biror narsa bo'lsa — tegmaymiz.
    """
    if user.is_staff or user.is_superuser or user.role in (Role.ADMIN, Role.ORGANIZATION):
        return False

    collector = Collector(using=router.db_for_write(User))
    try:
        collector.collect([user])
    except (ProtectedError, RestrictedError):
        return False

    for model, instances in collector.data.items():
        if model not in _HARMLESS and instances:
            return False

    for queryset in collector.fast_deletes:
        if queryset.model not in _HARMLESS and queryset.exists():
            return False

    # SET_NULL bog'lanishlar: u biror narsaning muallifi
    for batches in collector.field_updates.values():
        for batch in batches:
            if batch.exists() if hasattr(batch, 'exists') else len(batch):
                return False

    return True
