"""Bot uchun API (`/api/telegram/...`).

Sayt va bot bitta bazadan ishlaydi: bot statistikani, majburiy kanallarni va
reklama ro'yxatini shu yerdan oladi. Hammasi `X-Bot-Secret` bilan yopilgan —
tashqaridan hech kim chaqira olmaydi.
"""

import hmac
import json

from django.conf import settings
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.abroad.models import Peer
from apps.business.models import BusinessProfile
from apps.content.models import Announcement, Event, News
from apps.core.constants import Status
from apps.initiatives.models import Initiative, Problem, Solution
from apps.startups.models import Startup

from .models import Broadcast, ChannelJoin, RequiredChannel, Role, User


def bot_only(view):
    """Faqat bot chaqira oladi — maxfiy kalit mos kelishi shart."""

    def wrapper(request, *args, **kwargs):
        secret = getattr(settings, 'TELEGRAM_API_SECRET', '')
        provided = request.headers.get('X-Bot-Secret', '')
        if not secret or not hmac.compare_digest(provided, secret):
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


def body(request):
    """So'rov tanasidagi JSON (bo'lmasa — bo'sh lug'at)."""
    try:
        return json.loads(request.body or '{}')
    except ValueError:
        return {}


def channel_row(channel):
    return {
        'id': channel.pk,
        'chat_id': channel.chat_id,
        'title': channel.title,
        'username': channel.username,
        'link': channel.link,
        'is_active': channel.is_active,
        'joined': channel.joined_count,
    }


# --------------------------------------------------------------------------
# Adminlar
# --------------------------------------------------------------------------

def is_bot_admin(telegram_id):
    """Shu Telegram hisobi saytda admin bo'lsa — botda ham admin."""
    if not telegram_id:
        return None
    return User.objects.filter(
        Q(is_superuser=True) | Q(is_staff=True) | Q(role=Role.ADMIN),
        telegram_id=telegram_id,
    ).first()


@csrf_exempt
@require_http_methods(['GET'])
@bot_only
def bot_admin_check(request):
    """`/admin` bosilganda: bu odam admin bo'lishi kerakmi."""
    try:
        telegram_id = int(request.GET.get('telegram_id') or 0)
    except ValueError:
        telegram_id = 0

    user = is_bot_admin(telegram_id)
    return JsonResponse({
        'ok': True,
        'is_admin': user is not None,
        'name': user.full_name if user else '',
    })


# --------------------------------------------------------------------------
# Statistika
# --------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@bot_only
def bot_stats(request):
    """Sayt va botning umumiy holati — `/admin` menyusidagi «Statistika»."""
    today = timezone.localdate()
    week = timezone.now() - timezone.timedelta(days=7)

    users = User.objects.exclude(role=Role.ORGANIZATION).filter(is_superuser=False)
    bot_users = users.exclude(telegram_id=None)

    return JsonResponse({
        'ok': True,
        'users': {
            'total': users.count(),
            'bot': bot_users.count(),
            'today': users.filter(date_joined__date=today).count(),
            'week': users.filter(date_joined__gte=week).count(),
            'youth': users.filter(role=Role.YOUTH).count(),
            'entrepreneurs': users.filter(role=Role.ENTREPRENEUR).count(),
            'startuppers': users.filter(role=Role.STARTUPPER).count(),
        },
        'site': {
            'initiatives': Initiative.objects.filter(is_published=True).count(),
            'votes': Initiative.objects.aggregate(t=Sum('vote_count'))['t'] or 0,
            'problems': Problem.objects.count(),
            'solutions': Solution.objects.count(),
            'news': News.objects.count(),
            'events': Event.objects.count(),
            'announcements': Announcement.objects.count(),
            'peers': Peer.objects.filter(is_published=True).count(),
            'startups': Startup.objects.filter(status=Status.APPROVED).count(),
            'businesses': BusinessProfile.objects.filter(status=Status.APPROVED).count(),
        },
        'channels': [channel_row(channel) for channel in
                     RequiredChannel.objects.all().prefetch_related('joins')],
        'broadcasts': {
            'count': Broadcast.objects.count(),
            'last': _last_broadcast(),
        },
    })


def _last_broadcast():
    item = Broadcast.objects.first()
    if not item:
        return None
    return {'sent': item.sent, 'failed': item.failed, 'total': item.total,
            'created_at': item.created_at.isoformat()}


# --------------------------------------------------------------------------
# Majburiy kanallar
# --------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET', 'POST'])
@bot_only
def bot_channels(request):
    """GET — ro'yxat; POST — qo'shish yoki yangilash (chat_id bo'yicha)."""
    if request.method == 'GET':
        only_active = request.GET.get('faqat_faol') == '1'
        queryset = RequiredChannel.objects.all().prefetch_related('joins')
        if only_active:
            queryset = queryset.filter(is_active=True)
        return JsonResponse({'ok': True, 'results': [channel_row(c) for c in queryset]})

    data = body(request)
    chat_id = data.get('chat_id')
    if not chat_id:
        return JsonResponse({'ok': False, 'error': 'chat_id yo\'q'}, status=400)

    channel, created = RequiredChannel.objects.update_or_create(
        chat_id=int(chat_id),
        defaults={
            'title': (data.get('title') or 'Kanal')[:200],
            'username': (data.get('username') or '').lstrip('@')[:64],
            'invite_link': (data.get('invite_link') or '')[:300],
            'is_active': bool(data.get('is_active', True)),
            'added_by': data.get('added_by'),
        },
    )
    return JsonResponse({'ok': True, 'created': created, 'channel': channel_row(channel)})


@csrf_exempt
@require_http_methods(['POST', 'DELETE'])
@bot_only
def bot_channel_detail(request, pk):
    """DELETE — o'chirish; POST — faol / faolsiz qilish."""
    channel = get_object_or_404(RequiredChannel, pk=pk)

    if request.method == 'DELETE':
        title = channel.title
        channel.delete()
        return JsonResponse({'ok': True, 'deleted': True, 'title': title})

    channel.is_active = bool(body(request).get('is_active', not channel.is_active))
    channel.save(update_fields=['is_active'])
    return JsonResponse({'ok': True, 'channel': channel_row(channel)})


@csrf_exempt
@require_http_methods(['POST'])
@bot_only
def bot_channel_joins(request):
    """Obuna tekshiruvidan o'tganda: kim qaysi kanalga qo'shilgani qayd etiladi."""
    data = body(request)
    telegram_id = data.get('telegram_id')
    chat_ids = data.get('chat_ids') or []

    if not telegram_id:
        return JsonResponse({'ok': False, 'error': 'telegram_id yo\'q'}, status=400)

    added = 0
    for chat_id in chat_ids:
        channel = RequiredChannel.objects.filter(chat_id=chat_id).first()
        if not channel:
            continue
        _, created = ChannelJoin.objects.get_or_create(channel=channel,
                                                       telegram_id=int(telegram_id))
        added += int(created)

    return JsonResponse({'ok': True, 'added': added})


# --------------------------------------------------------------------------
# Reklama
# --------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['GET'])
@bot_only
def bot_users(request):
    """Reklama yuborish uchun Telegram ID'lar ro'yxati."""
    ids = list(User.objects
               .filter(is_active=True)
               .exclude(telegram_id=None)
               .values_list('telegram_id', flat=True))
    return JsonResponse({'ok': True, 'count': len(ids), 'ids': ids})


@csrf_exempt
@require_http_methods(['POST'])
@bot_only
def bot_broadcast(request):
    """Reklama boshlanganda yoziladi — keyin natijasi yangilanadi."""
    data = body(request)
    item = Broadcast.objects.create(
        text=data.get('text') or '',
        kind=data.get('kind') or Broadcast.Kind.TEXT,
        file_id=(data.get('file_id') or '')[:300],
        buttons=data.get('buttons') or [],
        total=max(int(data.get('total') or 0), 0),
        created_by=data.get('created_by'),
    )
    return JsonResponse({'ok': True, 'id': item.pk})


@csrf_exempt
@require_http_methods(['POST'])
@bot_only
def bot_broadcast_result(request, pk):
    """Yuborish tugagach: nechtasiga yetdi, nechtasi bloklagan."""
    item = get_object_or_404(Broadcast, pk=pk)
    data = body(request)

    item.sent = max(int(data.get('sent') or 0), 0)
    item.failed = max(int(data.get('failed') or 0), 0)
    item.blocked = max(int(data.get('blocked') or 0), 0)
    item.finished_at = timezone.now()
    item.save(update_fields=['sent', 'failed', 'blocked', 'finished_at'])

    return JsonResponse({'ok': True, 'sent': item.sent, 'failed': item.failed,
                         'blocked': item.blocked, 'total': item.total})
