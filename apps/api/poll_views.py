"""So'rovnomalar — masalan, «Viloyatning eng yaxshi mahalla yetakchisi».

Yo'l:
  1. Admin panelda (E'lonlar → So'rovnomalar) so'rovnoma va nomzodlarni
     kiritadi: ismi, mahallasi, tumani, rasmi.
  2. Saytda `/sorovnomalar/<slug>` sahifasida har kim bir marta ovoz beradi
     (kirgan bo'lishi shart — bitta Telegram akkaunt, bitta ovoz).
  3. Reyting har bir ovoz bilan yangilanadi; panelda natijalar alohida:
     o'rinlar, foizlar, tumanlar kesimi va kim ovoz bergani.

Ovozlar hisoblagichda emas — `PollVote` yozuvlaridan sanaladi, shuning uchun
bir vaqtda kelgan ovozlar ham, o'chirilgan nomzod ham sonni buzmaydi.
"""

import json
import re
from datetime import timedelta

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.bot_feed import enqueue_poll
from apps.content.models import Poll, PollOption, PollVote
from apps.core.cleanup import delete_with_files
from apps.core.constants import SamarqandDistrict

from .admin_views import IsPanelAdmin
from .serializers import absolute, validate_image_size

#: Ochiq sahifa ma'lumoti shuncha soniya keshda turadi — yuzlab odam sahifani
#: ochiq qoldirsa ham baza har soniyada sanab o'tirmaydi
PUBLIC_TTL = 5

#: Bitta so'rovnomada eng ko'pi bilan shuncha nomzod
MAX_OPTIONS = 300

#: Panelda ko'rinadigan oxirgi ovoz berganlar
VOTERS_LIMIT = 300


def _cache_key(slug):
    return f'poll:public:{slug}'


def _list_key():
    return 'poll:public:list'


def forget(poll):
    """Ochiq sahifa keshini tozalaydi — o'zgarish darhol ko'rinsin."""
    cache.delete_many([_cache_key(poll.slug), _list_key()])


def district_label(value):
    try:
        return SamarqandDistrict(value).label
    except ValueError:
        return value or ''


def with_votes(queryset=None):
    """Nomzodlar ovozlari soni bilan (`vote_total`)."""
    queryset = queryset if queryset is not None else PollOption.objects.all()
    return queryset.annotate(vote_total=Count('votes'))


def ranked(options):
    """Ovoz bo'yicha tartib. Teng ovozlilar bir xil o'rinda turadi: 1, 1, 3."""
    rows = sorted(options, key=lambda option: (-option.vote_total, option.order, option.pk))
    rank, previous = 0, None
    for index, option in enumerate(rows, 1):
        if option.vote_total != previous:
            rank, previous = index, option.vote_total
        option.rank = rank
    return rows


def percent(part, total):
    return round(part * 100 / total, 1) if total else 0


def option_data(request, option, total, reveal):
    data = {
        'id': option.pk,
        'name': option.name,
        'mahalla': option.mahalla,
        'district': option.district,
        'district_display': district_label(option.district),
        'note': option.note,
        'photo': absolute(request, option.photo),
    }
    if reveal:
        data.update(votes=option.vote_total, percent=percent(option.vote_total, total),
                    rank=option.rank)
    return data


def poll_data(request, poll, options, *, reveal=None, limit=None):
    """So'rovnoma va nomzodlari. `reveal` — ovozlar soni ko'rsatilsinmi."""
    reveal = poll.show_results if reveal is None else reveal
    total = sum(option.vote_total for option in options)
    rows = ranked(options) if reveal else sorted(options, key=lambda o: (o.order, o.pk))
    if limit:
        rows = rows[:limit]

    return {
        'id': poll.pk,
        'slug': poll.slug,
        'title': poll.title,
        'description': poll.description,
        'image': absolute(request, poll.image),
        'ends_at': poll.ends_at,
        'is_active': poll.is_active,
        'is_closed': poll.is_closed,
        'is_open': poll.is_open,
        'show_results': poll.show_results,
        'podium_min_votes': poll.podium_min_votes,
        'total_votes': total if reveal else None,
        'options_count': len(options),
        'options': [option_data(request, option, total, reveal) for option in rows],
        'created_at': poll.created_at,
    }


def public_polls():
    return Poll.objects.filter(is_active=True)


# --------------------------------------------------------------------------
# Ochiq sayt
# --------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def poll_list(request):
    """Saytdagi so'rovnomalar: ochiqlari oldinda, har birida peshqadam uchtalik."""
    data = cache.get(_list_key())
    if data is None:
        polls = public_polls().prefetch_related(
            Prefetch('options', queryset=with_votes()))[:50]
        rows = [poll_data(request, poll, list(poll.options.all()), limit=3) for poll in polls]
        # Ovoz berish davom etayotganlari oldinda
        rows.sort(key=lambda row: row['is_closed'])
        data = {'count': len(rows), 'results': rows}
        cache.set(_list_key(), data, PUBLIC_TTL)
    return Response(data)


def public_detail(request, poll):
    data = cache.get(_cache_key(poll.slug))
    if data is None:
        data = poll_data(request, poll, list(with_votes(poll.options.all())))
        cache.set(_cache_key(poll.slug), data, PUBLIC_TTL)
    return data


def my_vote(request, poll):
    if not request.user.is_authenticated:
        return None
    return (PollVote.objects.filter(poll=poll, user=request.user)
            .values_list('option_id', flat=True).first())


@api_view(['GET'])
@permission_classes([AllowAny])
def poll_detail(request, slug):
    poll = get_object_or_404(public_polls(), slug=slug)
    return Response({**public_detail(request, poll), 'my_vote': my_vote(request, poll)})


_DIGITS = re.compile(r'[0-9]{1,18}')


def parse_id(raw):
    """Faqat butun musbat son yoki raqamlardan iborat matn. `true`, `1.9`, `1e400` — yo'q."""
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw if raw > 0 else None
    if isinstance(raw, str) and _DIGITS.fullmatch(raw.strip()):
        return int(raw.strip()) or None
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def poll_vote(request, slug):
    """Ovoz berish — bir kishi bitta so'rovnomada bir marta.

    Ikki marta bosilsa (yoki ikki oynadan bir vaqtda) bazadagi cheklov
    ikkinchisini qaytaradi — ovoz ikki marta sanalmaydi.
    """
    poll = get_object_or_404(public_polls(), slug=slug)
    if poll.is_closed:
        return Response({'detail': "Ovoz berish yakunlangan."},
                        status=status.HTTP_400_BAD_REQUEST)

    body = request.data if isinstance(request.data, dict) else {}
    option_id = parse_id(body.get('option'))
    if option_id is None:
        return Response({'detail': "Nomzodni tanlang."}, status=status.HTTP_400_BAD_REQUEST)

    option = PollOption.objects.filter(poll=poll, pk=option_id).first()
    if option is None:
        return Response({'detail': "Bunday nomzod yo'q."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            PollVote.objects.create(poll=poll, option=option, user=request.user)
    except IntegrityError:
        return Response({
            'detail': "Siz bu so'rovnomada allaqachon ovoz bergansiz.",
            'my_vote': my_vote(request, poll),
        }, status=status.HTTP_409_CONFLICT)

    # Keshni o'chirmaymiz (aks holda ovoz oqimida har bir ko'ruvchi qayta sanatadi):
    # yangi holatni bir marta sanab, keshga o'zimiz yozamiz. Ovoz beruvchi esa
    # boshqa so'rov yozib qo'ygan eski nusxani emas, aynan shu yangisini oladi.
    data = poll_data(request, poll, list(with_votes(poll.options.all())))
    cache.set(_cache_key(poll.slug), data, PUBLIC_TTL)
    return Response({
        **data,
        'my_vote': option.pk,
        'message': f"Ovozingiz qabul qilindi — {option.name}. Rahmat!",
    }, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

class PanelPollSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    remove_image = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = Poll
        fields = ['title', 'description', 'image', 'remove_image', 'ends_at',
                  'is_active', 'show_results', 'podium_min_votes']

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Sarlavha juda qisqa.")
        return value

    def validate_image(self, value):
        return validate_image_size(value)

    def validate_podium_min_votes(self, value):
        if value > 1_000_000:
            raise serializers.ValidationError("Juda katta son.")
        return value

    def create(self, validated_data):
        validated_data.pop('remove_image', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        old_image = instance.image.name if instance.image else ''
        if validated_data.pop('remove_image', False) and 'image' not in validated_data:
            validated_data['image'] = ''
        item = super().update(instance, validated_data)
        if old_image and item.image.name != old_image:
            storage = item.image.storage
            transaction.on_commit(lambda: storage.delete(old_image))
        return item


class OptionInput(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    # Yangi nomzod rasmi `photo_<key>` nomli fayl bo'lib keladi
    key = serializers.CharField(max_length=40, required=False, allow_blank=True, default='')
    name = serializers.CharField(max_length=150, error_messages={
        'blank': "Nomzod ismini kiriting.", 'required': "Nomzod ismini kiriting."})
    mahalla = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    district = serializers.ChoiceField(choices=SamarqandDistrict.choices, required=False,
                                       allow_blank=True, default='')
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default='')
    remove_photo = serializers.BooleanField(required=False, default=False)
    # Formadagi qator raqami — xato xabari aynan shu qatorni ko'rsatsin
    pos = serializers.IntegerField(required=False, min_value=1)


def _first_error(errors):
    """`{'name': ['...']}` -> birinchi xato matni."""
    while isinstance(errors, (dict, list)):
        if not errors:
            return "Ma'lumot noto'g'ri."
        errors = next(iter(errors.values())) if isinstance(errors, dict) else errors[0]
    return str(errors)


def parse_options(request, poll):
    """Panel yuborgan nomzodlar ro'yxatini tekshiradi (bazaga hali yozmaydi).

    Hamma narsa shu yerda tekshiriladi — saqlash boshlangach xato chiqib,
    yarim yozilgan so'rovnoma qolib ketmasin.
    """
    raw = request.data.get('options')
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or '[]')
        except ValueError:
            raise serializers.ValidationError({'options': "Nomzodlar ro'yxati buzilgan."})
    if not isinstance(raw, list):
        raise serializers.ValidationError({'options': "Nomzodlar ro'yxati buzilgan."})
    if len(raw) < 2:
        raise serializers.ValidationError({'options': "Kamida 2 ta nomzod kiriting."})
    if len(raw) > MAX_OPTIONS:
        raise serializers.ValidationError(
            {'options': f"Nomzodlar {MAX_OPTIONS} tadan oshmasin."})

    existing = {option.pk: option for option in poll.options.all()} if poll else {}
    seen = set()
    rows = []

    for index, item in enumerate(raw, 1):
        item = item if isinstance(item, dict) else {}
        position = item.get('pos')
        number = position if isinstance(position, int) and position > 0 else index
        row = OptionInput(data=item)
        if not row.is_valid():
            raise serializers.ValidationError(
                {'options': f"{number}-nomzod: {_first_error(row.errors)}"})
        data = dict(row.validated_data)

        if data.get('id'):
            if data['id'] not in existing or data['id'] in seen:
                raise serializers.ValidationError(
                    {'options': f"{number}-nomzod topilmadi — sahifani yangilang."})
            seen.add(data['id'])

        photo = request.FILES.get(f"photo_{data['key']}") if data['key'] else None
        if photo is not None:
            try:
                serializers.ImageField().run_validation(photo)
                validate_image_size(photo)
            except serializers.ValidationError as error:
                raise serializers.ValidationError(
                    {'options': f"{number}-nomzod rasmi: {_first_error(error.detail)}"})
        data['photo'] = photo
        rows.append(data)

    return rows, existing


def voted_removals(rows, existing):
    """Ro'yxatdan olib tashlanayotgan, lekin ovozi bor nomzodlar (bazadagi joriy son bilan)."""
    kept = {row['id'] for row in rows if row.get('id')}
    removed = [pk for pk in existing if pk not in kept]
    if not removed:
        return []
    counts = (PollVote.objects.filter(option_id__in=removed)
              .values('option_id').annotate(total=Count('id')))
    return [{'id': row['option_id'], 'name': existing[row['option_id']].name,
             'votes': row['total']} for row in counts if row['total']]


def confirmed_ids(raw):
    """Admin o'chirishga rozi bo'lgan nomzodlar: `[1, 2]` yoki `"1,2"`."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip().startswith('[') else raw.split(',')
        except ValueError:
            return set()
    if not isinstance(raw, (list, tuple)):
        return set()
    return {value for value in (parse_id(item) for item in raw) if value}


def sync_options(poll, rows, existing):
    """Nomzodlarni ro'yxatga moslaydi: yangisini qo'shadi, borini yangilaydi,
    ro'yxatda yo'g'ini (ovozlari bilan) o'chiradi. Eski rasmlar saqlash
    muvaffaqiyatli tugagach o'chadi."""
    old_files = []
    keep = set()

    for order, row in enumerate(rows):
        option = existing.get(row.get('id')) or PollOption(poll=poll)
        option.name = row['name']
        option.mahalla = row['mahalla']
        option.district = row['district']
        option.note = row['note']
        option.order = order

        if row['photo'] is not None:
            if option.photo:
                old_files.append(option.photo.name)
            option.photo = row['photo']
        elif row['remove_photo'] and option.photo:
            old_files.append(option.photo.name)
            option.photo = ''

        option.save()
        keep.add(option.pk)

    removed = PollOption.objects.filter(poll=poll).exclude(pk__in=keep)
    old_files.extend(option.photo.name for option in removed if option.photo)
    removed.delete()

    storage = PollOption._meta.get_field('photo').storage
    transaction.on_commit(lambda: [storage.delete(name) for name in old_files])


def panel_poll_data(request, poll):
    options = list(poll.options.all())
    data = poll_data(request, poll, options, reveal=True)
    data['url'] = f'/sorovnomalar/{poll.slug}'
    # Tahrirlash formasi uchun nomzodlar asl tartibida
    data['editable'] = [
        {**option_data(request, option, data['total_votes'], False), 'votes': option.vote_total}
        for option in sorted(options, key=lambda o: (o.order, o.pk))
    ]
    return data


def save_poll(request, poll):
    created = poll is None
    serializer = PanelPollSerializer(poll, data=request.data, partial=not created)
    serializer.is_valid(raise_exception=True)

    # Faqat ko'rinishni almashtirish (ko'z tugmasi) — nomzodlarga tegmaymiz
    rows = None
    if created or 'options' in request.data:
        rows, existing = parse_options(request, poll)

        # Ovozi bor nomzod o'chsa, ovozlari ham butunlay o'chadi. Brauzerdagi
        # sonlar eskirgan bo'lishi mumkin — shuning uchun server o'zi tekshiradi
        # va admin aniq rozilik bermaguncha hech narsa yozilmaydi.
        risky = voted_removals(rows, existing)
        agreed = confirmed_ids(request.data.get('confirm_remove_voted'))
        # Admin ko'rmagan (keyin ovoz olgan) nomzod bo'lsa — yana so'raladi
        if any(row['id'] not in agreed for row in risky):
            names = ', '.join(f"{row['name']} ({row['votes']} ovoz)" for row in risky)
            return Response({
                'detail': f"Ovozi bor nomzodlar olib tashlanmoqda: {names}. "
                          "Ularning ovozlari ham o'chadi.",
                'remove_voted': risky,
            }, status=status.HTTP_409_CONFLICT)

    with transaction.atomic():
        poll = serializer.save()
        if rows is not None:
            sync_options(poll, rows, existing)

    # Botga e'lon — nomzodlar yozilgandan keyin bir marta (har nomzod uchun emas)
    if rows is not None:
        enqueue_poll(poll)

    forget(poll)
    poll = (Poll.objects.prefetch_related(Prefetch('options', queryset=with_votes()))
            .get(pk=poll.pk))
    return Response(panel_poll_data(request, poll),
                    status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class PanelPolls(APIView):
    """Panel: so'rovnomalar ro'yxati va yangisini qo'shish."""

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        polls = (Poll.objects.order_by('-created_at')
                 .prefetch_related(Prefetch('options', queryset=with_votes())))
        search = (request.query_params.get('q') or '').strip()
        if search:
            polls = polls.filter(Q(title__icontains=search)
                                 | Q(options__name__icontains=search)).distinct()
        return Response({
            'count': polls.count(),
            'results': [panel_poll_data(request, poll) for poll in polls[:60]],
        })

    def post(self, request):
        return save_poll(request, None)


class PanelPollDetail(APIView):
    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def patch(self, request, pk):
        return save_poll(request, get_object_or_404(Poll, pk=pk))

    def delete(self, request, pk):
        poll = get_object_or_404(Poll, pk=pk)
        forget(poll)
        delete_with_files(Poll.objects.filter(pk=poll.pk),
                          PollOption.objects.filter(poll_id=poll.pk))
        return Response({'deleted': True, 'label': poll.title})


@api_view(['GET'])
@permission_classes([IsPanelAdmin])
def panel_poll_results(request, pk):
    """Natijalar alohida: o'rinlar, tumanlar kesimi, kunlar bo'yicha va ovoz berganlar.

    `?option=<id>` — faqat shu nomzodga ovoz berganlar; `?q=` — ism yoki telefon.
    """
    poll = get_object_or_404(Poll, pk=pk)
    options = list(with_votes(poll.options.all()))
    data = poll_data(request, poll, options, reveal=True)
    data['url'] = f'/sorovnomalar/{poll.slug}'

    votes = PollVote.objects.filter(poll=poll)

    # Ovoz berganlar qaysi tumandan
    by_district = (votes.values('user__district').annotate(total=Count('id'))
                   .order_by('-total'))
    data['districts'] = [
        {'district': row['user__district'] or '',
         'label': district_label(row['user__district']) or "Ko'rsatilmagan",
         'votes': row['total']}
        for row in by_district
    ]

    # Oxirgi 30 kun — har kuni nechta ovoz
    since = timezone.now() - timedelta(days=30)
    daily = (votes.filter(created_at__gte=since)
             .annotate(day=TruncDate('created_at'))
             .values('day').annotate(total=Count('id')).order_by('day'))
    data['daily'] = [{'date': row['day'], 'votes': row['total']} for row in daily]

    voters = votes.select_related('user', 'option')
    option_id = request.query_params.get('option')
    if option_id and option_id.isdigit():
        voters = voters.filter(option_id=int(option_id))
    search = (request.query_params.get('q') or '').strip()
    if search:
        voters = voters.filter(Q(user__full_name__icontains=search)
                               | Q(user__phone__icontains=search))

    data['voters_count'] = voters.count()
    data['voters'] = [
        {
            'id': vote.pk,
            'user_id': vote.user_id,
            'full_name': vote.user.full_name,
            'phone': vote.user.phone,
            'district': district_label(vote.user.district),
            'option_id': vote.option_id,
            'option': vote.option.name,
            'created_at': vote.created_at,
        }
        for vote in voters[:VOTERS_LIMIT]
    ]
    return Response(data)
