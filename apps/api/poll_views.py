"""So'rovnomalar — masalan, «Viloyatning eng yaxshi mahalla yetakchisi».

Yo'l:
  1. Admin panelda (E'lonlar → So'rovnomalar) so'rovnoma va nomzodlarni
     kiritadi: ismi, mahallasi, tumani, rasmi.
  2. Saytda `/sorovnomalar/<slug>` sahifasida har kim bir marta ovoz beradi
     (kirgan bo'lishi shart — bitta Telegram akkaunt, bitta ovoz).
  3. Reyting har bir ovoz bilan yangilanadi; panelda natijalar alohida:
     o'rinlar, foizlar, tumanlar kesimi va kim ovoz bergani.

Yetakchilar tanlovi kabi yo'nalishli (nominatsiyali) so'rovnomada:
  - nomzodlar maxfiy havola orqali o'zi ariza beradi (`/sorovnomalar/ariza/<kalit>`),
    admin tasdiqlagandan keyingina saytda chiqadi;
  - reyting va foizlar har yo'nalish ichida alohida;
  - har kim har yo'nalishda bittadan ovoz beradi.

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
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts.bot_feed import enqueue_poll
from apps.accounts.telegram_views import normalize_phone
from apps.content.models import Poll, PollCategory, PollOption, PollVote
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

#: Bitta so'rovnomada eng ko'pi bilan shuncha yo'nalish
MAX_CATEGORIES = 20

#: Ko'rib chiqilmagan arizalar shundan oshsa, yangisi qabul qilinmaydi (spamga to'siq)
MAX_PENDING = 1000

APPROVED = PollOption.Status.APPROVED
PENDING = PollOption.Status.PENDING
REJECTED = PollOption.Status.REJECTED


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
    """Tasdiqlangan nomzodlar ovozlari soni bilan (`vote_total`).

    Ariza bergan, lekin hali tasdiqlanmagan nomzod hech qayerda chiqmaydi.
    """
    queryset = queryset if queryset is not None else PollOption.objects.all()
    return queryset.filter(status=APPROVED).annotate(vote_total=Count('votes'))


def with_options():
    """So'rovnoma + tasdiqlangan nomzodlari (ovozi bilan) + yo'nalishlari — bitta so'rovda."""
    return [Prefetch('options', queryset=with_votes()), 'categories']


def ranked(options):
    """Ovoz bo'yicha tartib. Teng ovozlilar bir xil o'rinda turadi: 1, 1, 3.

    Yo'nalishli so'rovnomada o'rin har yo'nalish ichida alohida sanaladi.
    """
    rows = sorted(options, key=lambda option: (-option.vote_total, option.order, option.pk))
    groups = {}
    for option in rows:
        seen, rank, previous = groups.get(option.category_id, (0, 0, None))
        seen += 1
        if option.vote_total != previous:
            rank, previous = seen, option.vote_total
        groups[option.category_id] = (seen, rank, previous)
        option.rank = rank
    return rows


def percent(part, total):
    return round(part * 100 / total, 1) if total else 0


def option_data(request, option, total, reveal):
    """`total` — nomzod turgan yo'nalishdagi (yo'nalish yo'q bo'lsa — butun) ovozlar."""
    data = {
        'id': option.pk,
        'category': option.category_id,
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


def category_rows(poll, options, totals, reveal):
    counts = {}
    for option in options:
        counts[option.category_id] = counts.get(option.category_id, 0) + 1
    return [
        {
            'id': category.pk,
            'title': category.title,
            'emoji': category.emoji,
            'options_count': counts.get(category.pk, 0),
            'total_votes': totals.get(category.pk, 0) if reveal else None,
        }
        for category in poll.categories.all()
    ]


def poll_data(request, poll, options, *, reveal=None, limit=None):
    """So'rovnoma va nomzodlari. `reveal` — ovozlar soni ko'rsatilsinmi.

    `limit` — ro'yxat kartasi uchun: oddiy so'rovnomada peshqadam `limit` ta,
    yo'nalishlisida har yo'nalishning birinchisi.
    """
    reveal = poll.show_results if reveal is None else reveal
    total = sum(option.vote_total for option in options)
    totals = {}
    for option in options:
        totals[option.category_id] = totals.get(option.category_id, 0) + option.vote_total
    categories = category_rows(poll, options, totals, reveal)

    rows = ranked(options) if reveal else sorted(options, key=lambda o: (o.order, o.pk))
    if limit:
        if categories:
            firsts = {}
            for option in rows:
                firsts.setdefault(option.category_id, option)
            rows = list(firsts.values())[:MAX_CATEGORIES]
        else:
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
        'categories': categories,
        'options': [option_data(request, option, totals[option.category_id], reveal)
                    for option in rows],
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
        polls = public_polls().prefetch_related(*with_options())[:50]
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


def my_votes(request, poll):
    """Kirgan foydalanuvchi ovoz bergan nomzodlar (yo'nalishli so'rovnomada bir nechta)."""
    if not request.user.is_authenticated:
        return []
    return list(PollVote.objects.filter(poll=poll, user=request.user)
                .order_by('created_at').values_list('option_id', flat=True))


def mine(request, poll):
    votes = my_votes(request, poll)
    # `my_vote` — oddiy so'rovnoma uchun (bitta ovoz), `my_votes` — hammasi
    return {'my_vote': votes[0] if votes else None, 'my_votes': votes}


@api_view(['GET'])
@permission_classes([AllowAny])
def poll_detail(request, slug):
    poll = get_object_or_404(public_polls(), slug=slug)
    return Response({**public_detail(request, poll), **mine(request, poll)})


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

    option = PollOption.objects.filter(poll=poll, pk=option_id, status=APPROVED).first()
    if option is None:
        return Response({'detail': "Bunday nomzod yo'q."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            PollVote.objects.create(poll=poll, option=option, user=request.user,
                                    category_id=option.category_id)
    except IntegrityError:
        return Response({
            'detail': ("Siz bu yo'nalishda allaqachon ovoz bergansiz." if option.category_id
                       else "Siz bu so'rovnomada allaqachon ovoz bergansiz."),
            **mine(request, poll),
        }, status=status.HTTP_409_CONFLICT)

    # Keshni o'chirmaymiz (aks holda ovoz oqimida har bir ko'ruvchi qayta sanatadi):
    # yangi holatni bir marta sanab, keshga o'zimiz yozamiz. Ovoz beruvchi esa
    # boshqa so'rov yozib qo'ygan eski nusxani emas, aynan shu yangisini oladi.
    data = poll_data(request, poll, list(with_votes(poll.options.all())))
    cache.set(_cache_key(poll.slug), data, PUBLIC_TTL)
    return Response({
        **data,
        **mine(request, poll),
        'my_vote': option.pk,
        'message': f"Ovozingiz qabul qilindi — {option.name}. Rahmat!",
    }, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# Nomzodning o'zi ariza berishi (maxfiy havola orqali)
# --------------------------------------------------------------------------

class ApplyThrottle(SimpleRateThrottle):
    """Bir manzildan ariza soni cheklangan — kirgan-kirmaganidan qat'i nazar."""

    scope = 'poll_apply'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


def _required(text):
    return {'required': text, 'blank': text, 'null': text}


class ApplySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, error_messages=_required(
        "Ism va familiyangizni yozing."))
    mahalla = serializers.CharField(max_length=150, error_messages=_required(
        "Mahallangiz nomini yozing."))
    district = serializers.ChoiceField(choices=SamarqandDistrict.choices, error_messages={
        **_required("Tumanni tanlang."), 'invalid_choice': "Tumanni tanlang."})
    category = serializers.IntegerField(required=False, allow_null=True, error_messages={
        'invalid': "Yo'nalishni tanlang."})
    phone = serializers.CharField(max_length=25, error_messages=_required(
        "Telefon raqamingizni yozing."))
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default='',
                                 error_messages={'max_length': "Qisqa ma'lumot 300 belgidan oshmasin."})
    photo = serializers.ImageField(error_messages={
        **_required("Rasmingizni yuklang."),
        'invalid_image': "Rasm ochilmadi — boshqa rasm tanlang (JPG yoki PNG).",
        'invalid': "Rasm ochilmadi — boshqa rasm tanlang (JPG yoki PNG).",
        'empty': "Rasm bo'sh — boshqa rasm tanlang."})

    def validate_name(self, value):
        value = ' '.join(value.split())
        if len(value) < 5 or ' ' not in value:
            raise serializers.ValidationError("Ism va familiyangizni to'liq yozing.")
        return value

    def validate_mahalla(self, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("Mahallangiz nomini yozing.")
        return value

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not 9 <= len(phone) - 1 <= 15:
            raise serializers.ValidationError("Telefon raqamini to'liq yozing: +998 90 123 45 67")
        return phone

    def validate_note(self, value):
        return value.strip()

    def validate_photo(self, value):
        return validate_image_size(value)

    def validate(self, attrs):
        poll = self.context['poll']
        categories = {category.pk: category for category in poll.categories.all()}
        chosen = attrs.get('category')
        if categories:
            if chosen not in categories:
                raise serializers.ValidationError({'category': "Yo'nalishni tanlang."})
            attrs['category'] = categories[chosen]
        else:
            attrs['category'] = None
        return attrs


def apply_info(request, poll):
    return {
        'title': poll.title,
        'description': poll.description,
        'image': absolute(request, poll.image),
        'accepts': poll.accepts_applications,
        'categories': [{'id': category.pk, 'title': category.title, 'emoji': category.emoji}
                       for category in poll.categories.all()],
        'districts': [{'value': value, 'label': label}
                      for value, label in SamarqandDistrict.choices],
    }


class PollApply(APIView):
    """Nomzod o'zi ariza beradi: ismi, mahallasi, tumani, yo'nalishi, rasmi.

    Kirish shart emas — havolaning o'zi kalit. Ariza admin tasdiqlaguncha
    saytda ko'rinmaydi.
    """

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def get_throttles(self):
        return [ApplyThrottle()] if self.request.method == 'POST' else []

    def poll(self, token):
        return get_object_or_404(Poll.objects.prefetch_related('categories'), apply_token=token)

    def get(self, request, token):
        return Response(apply_info(request, self.poll(token)))

    def post(self, request, token):
        poll = self.poll(token)
        if not poll.accepts_applications:
            return Response({'detail': "Ariza qabul qilish yakunlangan."},
                            status=status.HTTP_400_BAD_REQUEST)

        done = "Arizangiz qabul qilindi! Tashkilotchilar ko'rib chiqqach, saytda chiqadi."
        # Odam ko'rmaydigan maydon — to'ldirilgan bo'lsa, yuborgan bot. Unga
        # «qabul qilindi» deymiz, lekin hech narsa yozmaymiz
        if str(request.data.get('website') or '').strip():
            return Response({'detail': done}, status=status.HTTP_201_CREATED)

        serializer = ApplySerializer(data=request.data, context={'poll': poll})
        if not serializer.is_valid():
            field = next(iter(serializer.errors), None)
            return Response({'detail': _first_error(serializer.errors), 'field': field},
                            status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        if PollOption.objects.filter(poll=poll, status=PENDING).count() >= MAX_PENDING:
            return Response({'detail': "Arizalar juda ko'p — birozdan keyin qayta urinib ko'ring."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        if (PollOption.objects.filter(poll=poll, category=data['category'], phone=data['phone'])
                .exclude(status=REJECTED).exists()):
            return Response({'detail': "Bu raqam bilan shu yo'nalishga ariza allaqachon yuborilgan.",
                             'field': 'phone'}, status=status.HTTP_409_CONFLICT)

        option = PollOption.objects.create(
            poll=poll, category=data['category'], status=PENDING,
            name=data['name'], mahalla=data['mahalla'], district=data['district'],
            note=data['note'], phone=data['phone'], photo=data['photo'],
        )
        return Response({
            'detail': done,
            'name': option.name,
            'category': data['category'].title if data['category'] else '',
        }, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

def truthy(value):
    return value is True or str(value).strip().lower() in ('1', 'true', 'on', 'yes')


class OptionalBoolean(serializers.BooleanField):
    """Formada yuborilmagan bo'lsa — «yo'q» emas, umuman tegilmaydi (model standarti qoladi)."""

    default_empty_html = serializers.empty


class PanelPollSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    # Ariza qabul qilish standart holatda ochiq — panel formasi uni yubormaydi
    apply_open = OptionalBoolean(required=False)
    remove_image = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = Poll
        fields = ['title', 'description', 'image', 'remove_image', 'ends_at',
                  'is_active', 'show_results', 'podium_min_votes', 'apply_open']

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
    # Yo'nalish: mavjudining id'si yoki shu formada qo'shilayotganining `key`i
    category = serializers.CharField(max_length=40, required=False, allow_blank=True,
                                     allow_null=True, default='')
    remove_photo = serializers.BooleanField(required=False, default=False)
    # Formadagi qator raqami — xato xabari aynan shu qatorni ko'rsatsin
    pos = serializers.IntegerField(required=False, min_value=1)


class CategoryInput(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    key = serializers.CharField(max_length=40, required=False, allow_blank=True, default='')
    title = serializers.CharField(max_length=150, error_messages={
        'blank': "Yo'nalish nomini yozing.", 'required': "Yo'nalish nomini yozing."})
    emoji = serializers.CharField(max_length=8, required=False, allow_blank=True, default='')


def _json_list(request, name, broken):
    # Yuborilmagan bo'lsa — bo'sh ro'yxat (masalan, nomzodlarsiz yangi so'rovnoma)
    raw = request.data.get(name, [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or '[]')
        except ValueError:
            raise serializers.ValidationError({name: broken})
    if not isinstance(raw, list):
        raise serializers.ValidationError({name: broken})
    return raw


def parse_categories(request, poll):
    """Yo'nalishlar ro'yxati. Nomzodi bor yo'nalishni olib tashlab bo'lmaydi —
    aks holda nomzodlar ovozlari bilan birga yo'qolardi."""
    raw = _json_list(request, 'categories', "Yo'nalishlar ro'yxati buzilgan.")
    if len(raw) > MAX_CATEGORIES:
        raise serializers.ValidationError(
            {'categories': f"Yo'nalishlar {MAX_CATEGORIES} tadan oshmasin."})

    existing = {category.pk: category for category in poll.categories.all()} if poll else {}
    rows, seen, keys = [], set(), set()
    for number, item in enumerate(raw, 1):
        row = CategoryInput(data=item if isinstance(item, dict) else {})
        if not row.is_valid():
            raise serializers.ValidationError(
                {'categories': f"{number}-yo'nalish: {_first_error(row.errors)}"})
        data = dict(row.validated_data)
        data['title'] = ' '.join(data['title'].split())
        if data.get('id'):
            if data['id'] not in existing or data['id'] in seen:
                raise serializers.ValidationError(
                    {'categories': f"{number}-yo'nalish topilmadi — sahifani yangilang."})
            seen.add(data['id'])
        else:
            if not data['key'] or data['key'] in keys:
                raise serializers.ValidationError(
                    {'categories': f"{number}-yo'nalish: kalit noto'g'ri — sahifani yangilang."})
            keys.add(data['key'])
        rows.append(data)

    removed = [pk for pk in existing if pk not in seen]
    if removed:
        busy = (PollOption.objects.filter(category_id__in=removed)
                .values('category_id').annotate(total=Count('id')))
        for row in busy:
            title = existing[row['category_id']].title
            raise serializers.ValidationError({'categories': (
                f"«{title}» yo'nalishida {row['total']} ta nomzod (ariza) bor — avval ularni "
                "o'chiring yoki boshqa yo'nalishga o'tkazing.")})
    return rows, existing


def category_refs(categories, poll):
    """Nomzod qatorida yo'nalishga ishora qilish mumkin bo'lgan qiymatlar."""
    if categories is not None:
        return ({str(row['id']) for row in categories if row.get('id')}
                | {row['key'] for row in categories if not row.get('id')})
    return {str(category.pk) for category in poll.categories.all()} if poll else set()


def sync_categories(poll, rows, existing):
    """Yo'nalishlarni ro'yxatga moslaydi; `{ishora: yo'nalish}` qaytaradi."""
    refs = {}
    keep = set()
    for order, row in enumerate(rows):
        category = existing.get(row.get('id')) or PollCategory(poll=poll)
        category.title = row['title']
        category.emoji = row['emoji'].strip()
        category.order = order
        category.save()
        keep.add(category.pk)
        refs[str(row['id']) if row.get('id') else row['key']] = category
    PollCategory.objects.filter(poll=poll).exclude(pk__in=keep).delete()
    return refs


def _first_error(errors):
    """`{'name': ['...']}` -> birinchi xato matni."""
    while isinstance(errors, (dict, list)):
        if not errors:
            return "Ma'lumot noto'g'ri."
        errors = next(iter(errors.values())) if isinstance(errors, dict) else errors[0]
    return str(errors)


def parse_options(request, poll, refs):
    """Panel yuborgan nomzodlar ro'yxatini tekshiradi (bazaga hali yozmaydi).

    Hamma narsa shu yerda tekshiriladi — saqlash boshlangach xato chiqib,
    yarim yozilgan so'rovnoma qolib ketmasin.

    Ro'yxatda faqat tasdiqlangan nomzodlar: ko'rib chiqilayotgan arizalarga
    bu forma tegmaydi (ular «Arizalar» bo'limida). `refs` — yo'nalishlar;
    bo'sh bo'lmasa, har nomzodning yo'nalishi bo'lishi shart.

    Nomzod kiritish shart emas — odatda ular havola orqali o'zi ariza beradi.
    """
    raw = _json_list(request, 'options', "Nomzodlar ro'yxati buzilgan.")
    if len(raw) > MAX_OPTIONS:
        raise serializers.ValidationError(
            {'options': f"Nomzodlar {MAX_OPTIONS} tadan oshmasin."})

    existing = ({option.pk: option for option in poll.options.filter(status=APPROVED)}
                if poll else {})
    voted = set(PollVote.objects.filter(option_id__in=existing)
                .values_list('option_id', flat=True).distinct()) if existing else set()
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

        data['category'] = str(data.get('category') or '').strip()
        if refs and data['category'] not in refs:
            raise serializers.ValidationError(
                {'options': f"{number}-nomzod: yo'nalishni tanlang."})
        if not refs:
            data['category'] = ''
        # Ovozlar yo'nalishga bog'langan — ovozi bor nomzodni boshqasiga o'tkazib bo'lmaydi
        if data.get('id') in voted:
            current = existing[data['id']].category_id
            if data['category'] != (str(current) if current else ''):
                raise serializers.ValidationError({'options': (
                    f"{number}-nomzodning ovozlari bor — yo'nalishini o'zgartirib bo'lmaydi.")})

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


def sync_options(poll, rows, existing, categories):
    """Nomzodlarni ro'yxatga moslaydi: yangisini qo'shadi, borini yangilaydi,
    ro'yxatda yo'g'ini (ovozlari bilan) o'chiradi. Eski rasmlar saqlash
    muvaffaqiyatli tugagach o'chadi. Arizalar (tasdiqlanmaganlar) tegilmaydi."""
    old_files = []
    keep = set()

    for order, row in enumerate(rows):
        option = existing.get(row.get('id')) or PollOption(poll=poll, status=APPROVED)
        option.category = categories.get(row['category'])
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

    removed = PollOption.objects.filter(poll=poll, status=APPROVED).exclude(pk__in=keep)
    old_files.extend(option.photo.name for option in removed if option.photo)
    removed.delete()

    storage = PollOption._meta.get_field('photo').storage
    transaction.on_commit(lambda: [storage.delete(name) for name in old_files])


def panel_polls():
    """Panel ro'yxati: nomzodlar, yo'nalishlar va ko'rib chiqilmagan arizalar soni."""
    return (Poll.objects.prefetch_related(*with_options())
            .annotate(pending_count=Count('options', filter=Q(options__status=PENDING),
                                          distinct=True)))


def panel_poll_data(request, poll):
    options = list(poll.options.all())
    data = poll_data(request, poll, options, reveal=True)
    data['url'] = f'/sorovnomalar/{poll.slug}'
    data['apply_open'] = poll.apply_open
    data['apply_url'] = f'/sorovnomalar/ariza/{poll.apply_token}' if poll.apply_token else None
    data['pending_count'] = getattr(poll, 'pending_count', 0)
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

    categories = existing_categories = None
    if 'categories' in request.data:
        categories, existing_categories = parse_categories(request, poll)
    refs = category_refs(categories, poll)

    # Faqat ko'rinishni almashtirish (ko'z tugmasi) — nomzodlarga tegmaymiz
    rows = None
    if created or 'options' in request.data:
        rows, existing = parse_options(request, poll, refs)

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
        # Ariza havolasi har so'rovnomada bor (model o'zi yaratadi); bu — admin yangisini so'raganda
        if truthy(request.data.get('new_apply_link')):
            poll.new_apply_token()
            poll.save(update_fields=['apply_token', 'updated_at'])
        if categories is not None:
            refs = sync_categories(poll, categories, existing_categories)
        else:
            refs = {str(category.pk): category for category in poll.categories.all()}
        if rows is not None:
            sync_options(poll, rows, existing, refs)

    # Botga e'lon — nomzodlar yozilgandan keyin bir marta (har nomzod uchun emas)
    if rows is not None:
        enqueue_poll(poll)

    forget(poll)
    poll = panel_polls().get(pk=poll.pk)
    return Response(panel_poll_data(request, poll),
                    status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class PanelPolls(APIView):
    """Panel: so'rovnomalar ro'yxati va yangisini qo'shish."""

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        polls = panel_polls().order_by('-created_at')
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


def application_data(request, option):
    return {
        'id': option.pk,
        'name': option.name,
        'mahalla': option.mahalla,
        'district': option.district,
        'district_display': district_label(option.district),
        'note': option.note,
        'phone': option.phone,
        'photo': absolute(request, option.photo),
        'category': option.category_id,
        'category_title': option.category.title if option.category else '',
        'status': option.status,
        'votes': option.vote_total,
        'created_at': option.created_at,
    }


def status_counts(poll):
    counts = dict(PollOption.objects.filter(poll=poll).values_list('status')
                  .annotate(total=Count('id')))
    return {value: counts.get(value, 0) for value in PollOption.Status.values}


class PanelPollApplications(APIView):
    """Panel: havola orqali kelgan arizalar. `?holat=pending|approved|rejected`, `?q=`."""

    permission_classes = [IsPanelAdmin]

    def get(self, request, pk):
        poll = get_object_or_404(Poll, pk=pk)
        options = (PollOption.objects.filter(poll=poll).select_related('category')
                   .annotate(vote_total=Count('votes')).order_by('-created_at', '-pk'))
        state = request.query_params.get('holat') or PENDING
        if state in PollOption.Status.values:
            options = options.filter(status=state)
        category = parse_id(request.query_params.get('yonalish') or '')
        if category:
            options = options.filter(category_id=category)
        search = (request.query_params.get('q') or '').strip()
        if search:
            options = options.filter(Q(name__icontains=search) | Q(mahalla__icontains=search)
                                     | Q(phone__icontains=search))
        return Response({
            'poll': {
                'id': poll.pk,
                'title': poll.title,
                'url': f'/sorovnomalar/{poll.slug}',
                'apply_open': poll.apply_open,
                'apply_url': (f'/sorovnomalar/ariza/{poll.apply_token}'
                              if poll.apply_token else None),
                'categories': [{'id': category.pk, 'title': category.title,
                                'emoji': category.emoji} for category in poll.categories.all()],
            },
            'counts': status_counts(poll),
            'results': [application_data(request, option) for option in options[:500]],
        })


class PanelPollApplication(APIView):
    """Panel: arizani tasdiqlash / rad etish / yo'nalishini almashtirish / o'chirish."""

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, FormParser]

    def option(self, pk, option_id):
        return get_object_or_404(
            PollOption.objects.select_related('poll', 'category').annotate(vote_total=Count('votes')),
            poll_id=pk, pk=option_id)

    def patch(self, request, pk, option_id):
        option = self.option(pk, option_id)
        poll = option.poll
        fields = []

        if 'category' in request.data:
            category = poll.categories.filter(pk=parse_id(request.data.get('category'))).first()
            if category is None:
                return Response({'detail': "Yo'nalishni tanlang."},
                                status=status.HTTP_400_BAD_REQUEST)
            if category.pk != option.category_id:
                if option.vote_total:
                    return Response(
                        {'detail': "Nomzodning ovozlari bor — yo'nalishini o'zgartirib bo'lmaydi."},
                        status=status.HTTP_400_BAD_REQUEST)
                option.category = category
                fields.append('category')

        if 'status' in request.data:
            new = request.data.get('status')
            if new not in PollOption.Status.values:
                return Response({'detail': "Holat noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST)
            if new != option.status:
                if option.status == APPROVED and option.vote_total:
                    return Response({'detail': (
                        "Nomzodning ovozlari bor — uni faqat so'rovnomani tahrirlash oynasidan "
                        "olib tashlash mumkin.")}, status=status.HTTP_400_BAD_REQUEST)
                if new == APPROVED:
                    # Tasdiqlangan nomzod ro'yxat oxiriga qo'shiladi
                    last = (PollOption.objects.filter(poll=poll, status=APPROVED)
                            .order_by('-order').values_list('order', flat=True).first())
                    option.order = min((last or 0) + 1, 32767)
                    fields.append('order')
                option.status = new
                fields.append('status')

        if fields:
            option.save(update_fields=[*fields, 'updated_at'])
            forget(poll)
            if option.status == APPROVED:
                enqueue_poll(poll)
        return Response({**application_data(request, option), 'counts': status_counts(poll)})

    def delete(self, request, pk, option_id):
        option = self.option(pk, option_id)
        if option.status == APPROVED:
            return Response({'detail': (
                "Tasdiqlangan nomzod so'rovnomani tahrirlash oynasidan olib tashlanadi.")},
                status=status.HTTP_400_BAD_REQUEST)
        delete_with_files(PollOption.objects.filter(pk=option.pk))
        return Response({'deleted': True, 'label': option.name,
                         'counts': status_counts(option.poll)})


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
            'category': vote.category_id,
            'created_at': vote.created_at,
        }
        for vote in voters[:VOTERS_LIMIT]
    ]
    return Response(data)
