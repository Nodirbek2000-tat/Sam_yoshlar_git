"""Investitsiya takliflari.

Yo'l:
  1. Investor startap sahifasida «Investitsiya kiritaman» ni bosadi va
     ismi, raqami, Telegram'ini qoldiradi.
  2. Startap egasiga saytda bildirishnoma va botda xabar boradi — investor
     bilan darhol bog'lana oladi.
  3. Ega taklifni qabul qiladi (yoki rad etadi) — investorga xabar boradi.
  4. Keyingi kirishda sayt egadan suhbat natijasini so'raydi.
  5. Hammasi panelda «Investitsiya takliflari» bo'limida ko'rinadi.
"""

import re
from datetime import timedelta
from html import escape

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.bot_messages import send_personal
from apps.accounts.telegram_views import normalize_phone
from apps.cabinet.models import Notification
from apps.startups.models import InvestmentOffer, OfferOutcome, OfferStatus

from . import serializers as s
from .admin_views import IsPanelAdmin
from .views import public_startups

#: Qabul qilingach shuncha vaqtdan keyin sayt egadan fikr so'raydi
FEEDBACK_DELAY = timedelta(minutes=30)
#: «Keyinroq» bosilsa yoki muzokara davom etayotgan bo'lsa — qayta so'rash
FEEDBACK_SNOOZE = timedelta(days=2)
FEEDBACK_RECHECK = timedelta(days=7)

#: Bir odam kuniga shuncha taklif yubora oladi (spamdan himoya)
DAILY_LIMIT = 10

CABINET_LINK = '/kabinet/investitsiya'

_TELEGRAM = re.compile(r'^[A-Za-z][A-Za-z0-9_]{3,31}$')


def clean_telegram(value):
    """`@ali`, `t.me/ali`, `https://t.me/ali` -> `ali`. Noto'g'ri bo'lsa — `None`."""
    value = (value or '').strip()
    value = re.sub(r'^(https?://)?(t\.me|telegram\.me)/', '', value, flags=re.IGNORECASE)
    value = value.lstrip('@').split('?')[0].strip('/')
    if not value:
        return ''
    return value if _TELEGRAM.match(value) else None


class OfferCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, trim_whitespace=True)
    phone = serializers.CharField(max_length=25)
    telegram = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate_full_name(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Ism va familiyangizni to'liq yozing.")
        return value

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not 9 <= len(phone) - 1 <= 15:
            raise serializers.ValidationError("Telefon raqamini to'liq yozing: +998 90 123 45 67")
        return phone

    def validate_telegram(self, value):
        username = clean_telegram(value)
        if username is None:
            raise serializers.ValidationError("Telegram manzilini @username ko'rinishida yozing.")
        return username


# --------------------------------------------------------------------------
# Ko'rinishlar uchun yordamchilar
# --------------------------------------------------------------------------

def person(request, user):
    """Hisobga havola uchun: `/insonlar/<id>` sahifasi ochiladi."""
    if not user:
        return None
    return {'id': user.pk, 'full_name': user.full_name, 'initials': user.initials,
            'avatar': s.absolute(request, user.avatar)}


def startup_brief(request, startup):
    return {'id': startup.pk, 'name': startup.name,
            'logo_url': s.absolute(request, startup.logo)}


def offer_state(offer):
    return {'id': offer.pk, 'status': offer.status, 'status_display': offer.get_status_display(),
            'created_at': offer.created_at, 'responded_at': offer.responded_at}


def offer_row(request, offer, contacts=True):
    """Taklifning to'liq ko'rinishi. `contacts=False` — investorning o'ziga (aloqasiz)."""
    row = {**offer_state(offer), 'startup': startup_brief(request, offer.startup)}
    if contacts:
        row.update({
            'investor': person(request, offer.investor),
            'full_name': offer.full_name, 'phone': offer.phone, 'telegram': offer.telegram,
            'outcome': offer.outcome, 'outcome_display': offer.get_outcome_display(),
            'feedback': offer.feedback, 'feedback_at': offer.feedback_at,
        })
    return row


def pending_feedback(user):
    """Ega fikr bildirishi kerak bo'lgan taklif (vaqti kelgan bo'lsa) yoki `None`."""
    offer = (InvestmentOffer.objects
             .filter(startup__user=user, status=OfferStatus.ACCEPTED,
                     feedback_ask_after__lte=timezone.now())
             .select_related('startup').order_by('feedback_ask_after').first())
    if not offer:
        return None
    return {'id': offer.pk, 'startup_name': offer.startup.name,
            'investor_name': offer.full_name,
            # Oldin «muzokara davom etmoqda» degan — endi yakunini so'raymiz
            'follow_up': offer.outcome == OfferOutcome.TALKING}


# --------------------------------------------------------------------------
# Investor: taklif yuborish
# --------------------------------------------------------------------------

class StartupInvest(APIView):
    """Startap sahifasidagi tugma: holatni bilish (GET) va taklif yuborish (POST)."""

    def get_permissions(self):
        # Holatni mehmon ham so'raydi (tugma «kirish»ga yuborishi uchun) — yuborish esa faqat kirganlarga
        return [AllowAny()] if self.request.method == 'GET' else [IsAuthenticated()]

    def state(self, request, startup):
        user = request.user
        offer = InvestmentOffer.objects.filter(startup=startup, investor=user).first()
        return {
            'is_owner': startup.user_id == user.pk,
            'offer': offer_state(offer) if offer else None,
            'prefill': {'full_name': user.full_name, 'phone': user.phone,
                        'telegram': user.telegram_username},
        }

    def get(self, request, pk):
        startup = get_object_or_404(public_startups(), pk=pk)
        if not request.user.is_authenticated:
            return Response({'authenticated': False})
        return Response({'authenticated': True, **self.state(request, startup)})

    def post(self, request, pk):
        startup = get_object_or_404(public_startups().select_related('user'), pk=pk)
        user = request.user

        if startup.user_id == user.pk:
            return Response({'detail': "O'z startapingizga taklif yubora olmaysiz."},
                            status=status.HTTP_400_BAD_REQUEST)
        if InvestmentOffer.objects.filter(startup=startup, investor=user).exists():
            return Response({'detail': "Siz bu startapga taklif yuborgansiz.",
                             **self.state(request, startup)}, status=status.HTTP_409_CONFLICT)

        today = timezone.now() - timedelta(days=1)
        if InvestmentOffer.objects.filter(investor=user,
                                          created_at__gte=today).count() >= DAILY_LIMIT:
            return Response({'detail': "Bugun juda ko'p taklif yubordingiz. Ertaga urinib ko'ring."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)

        serializer = OfferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                offer = InvestmentOffer.objects.create(
                    startup=startup, investor=user, **serializer.validated_data)
        except IntegrityError:
            # Tugma ikki marta bosilgan — birinchisi saqlangan
            return Response(self.state(request, startup), status=status.HTTP_409_CONFLICT)

        notify_owner(offer)
        return Response(self.state(request, startup), status=status.HTTP_201_CREATED)


def notify_owner(offer):
    """Startap egasiga: saytda bildirishnoma va botda investorning aloqasi."""
    owner = offer.startup.user
    if not owner:
        # Hisobsiz (import qilingan) startap — taklif panelda ko'rinadi
        return

    Notification.objects.create(
        user=owner,
        title="Startapingizga investor qiziqish bildirdi",
        message=f"«{offer.startup.name}» — {offer.full_name}, {offer.phone}. Bog'laning va taklifni qabul qiling.",
        type='success',
        link=CABINET_LINK,
    )

    lines = [
        "💼 <b>Startapingizga investor qiziqish bildirdi!</b>",
        "",
        f"🚀 Startap: <b>{escape(offer.startup.name)}</b>",
        f"👤 Ism: {escape(offer.full_name)}",
        f"📞 Telefon: {escape(offer.phone)}",
    ]
    buttons = []
    if offer.telegram:
        lines.append(f"✈️ Telegram: @{escape(offer.telegram)}")
        buttons.append({'text': "✍️ Telegramda yozish", 'url': f"https://t.me/{offer.telegram}"})
    lines += ["", "Iloji boricha tezroq bog'laning, so'ng saytda taklifni qabul qiling."]
    buttons.append({'text': "📋 Taklifni ko'rish", 'url': CABINET_LINK})

    send_personal(owner, "\n".join(lines), buttons)


# --------------------------------------------------------------------------
# Kabinet: kelgan va yuborilgan takliflar
# --------------------------------------------------------------------------

class MyOffers(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        received = (InvestmentOffer.objects.filter(startup__user=request.user)
                    .select_related('startup', 'investor'))
        sent = InvestmentOffer.objects.filter(investor=request.user).select_related('startup')

        return Response({
            'new': received.filter(status=OfferStatus.NEW).count(),
            'received': [offer_row(request, offer) for offer in received[:100]],
            'sent': [offer_row(request, offer, contacts=False) for offer in sent[:100]],
        })


def own_offer(request, pk):
    """Faqat startap egasi o'ziga kelgan taklifni boshqaradi."""
    return get_object_or_404(
        InvestmentOffer.objects.select_related('startup', 'investor'),
        pk=pk, startup__user=request.user)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_offer(request, pk):
    """Ega taklifni qabul qiladi yoki rad etadi: `{"action": "accept" | "decline"}`."""
    offer = own_offer(request, pk)
    action = request.data.get('action')
    if action not in ('accept', 'decline'):
        return Response({'detail': "Noma'lum amal."}, status=status.HTTP_400_BAD_REQUEST)

    wanted = OfferStatus.ACCEPTED if action == 'accept' else OfferStatus.DECLINED
    if offer.status != wanted:
        now = timezone.now()
        offer.status = wanted
        offer.responded_at = now
        # Qabul qilingach biroz o'tib sayt suhbat natijasini so'raydi
        offer.feedback_ask_after = now + FEEDBACK_DELAY if action == 'accept' else None
        offer.save(update_fields=['status', 'responded_at', 'feedback_ask_after', 'updated_at'])
        notify_investor(offer)

    return Response(offer_row(request, offer))


def notify_investor(offer):
    """Investorga: ega taklifni qabul qildi yoki rad etdi."""
    investor = offer.investor
    if not investor:
        return

    name = offer.startup.name
    link = f'/startaplar/{offer.startup_id}'

    if offer.status == OfferStatus.ACCEPTED:
        Notification.objects.create(
            user=investor, title="Taklifingiz qabul qilindi",
            message=f"«{name}» asoschisi taklifingizni qabul qildi. Tez orada siz bilan bog'lanadi.",
            type='success', link=CABINET_LINK)
        send_personal(investor, "\n".join([
            "✅ <b>Taklifingiz qabul qilindi!</b>",
            "",
            f"«{escape(name)}» asoschisi investitsiya taklifingizni qabul qildi "
            "va tez orada siz bilan bog'lanadi.",
        ]), [{'text': "🚀 Startapni ochish", 'url': link}])
    else:
        Notification.objects.create(
            user=investor, title="Taklifingizga javob keldi",
            message=f"«{name}» asoschisi hozircha taklifni qabul qilmadi.",
            type='info', link=CABINET_LINK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def offer_feedback(request, pk):
    """Ega suhbat natijasini aytadi yoki «keyinroq» deydi.

    `{"later": true}` — ikki kundan keyin yana so'raladi.
    `{"outcome": "deal" | "talking" | "no_deal", "feedback": "..."}` — fikr saqlanadi.
    """
    offer = own_offer(request, pk)
    if offer.status != OfferStatus.ACCEPTED:
        return Response({'detail': "Avval taklifni qabul qiling."},
                        status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    if request.data.get('later'):
        offer.feedback_ask_after = now + FEEDBACK_SNOOZE
        offer.save(update_fields=['feedback_ask_after', 'updated_at'])
        return Response(offer_row(request, offer))

    outcome = request.data.get('outcome')
    if outcome not in OfferOutcome.values:
        return Response({'detail': "Natijani tanlang."}, status=status.HTTP_400_BAD_REQUEST)

    offer.outcome = outcome
    offer.feedback = str(request.data.get('feedback') or '').strip()[:2000]
    offer.feedback_at = now
    # Muzokara tugamagan bo'lsa — bir haftadan keyin yakunini so'raymiz
    offer.feedback_ask_after = now + FEEDBACK_RECHECK if outcome == OfferOutcome.TALKING else None
    offer.save(update_fields=['outcome', 'feedback', 'feedback_at', 'feedback_ask_after',
                              'updated_at'])
    return Response(offer_row(request, offer))


# --------------------------------------------------------------------------
# Panel: hamma takliflar
# --------------------------------------------------------------------------

class PanelOffers(APIView):
    """Kim kimga taklif yubordi, nechtasi qabul qilindi, kim fikr bildirdi.

    Filtrlar: `?holat=new|accepted|declined`, `?fikr=bor|yoq`,
    `?natija=deal|talking|no_deal`, `?q=` (startap yoki odam nomi).
    """

    permission_classes = [IsPanelAdmin]
    page_size = 25

    def get(self, request):
        everything = InvestmentOffer.objects.all()
        totals = everything.aggregate(
            total=Count('id'),
            new=Count('id', filter=Q(status=OfferStatus.NEW)),
            accepted=Count('id', filter=Q(status=OfferStatus.ACCEPTED)),
            declined=Count('id', filter=Q(status=OfferStatus.DECLINED)),
            feedback=Count('id', filter=Q(feedback_at__isnull=False)),
            deals=Count('id', filter=Q(outcome=OfferOutcome.DEAL)),
            talking=Count('id', filter=Q(outcome=OfferOutcome.TALKING)),
            no_deal=Count('id', filter=Q(outcome=OfferOutcome.NO_DEAL)),
            # Qabul qilgan, lekin hali fikr bildirmaganlar
            waiting_feedback=Count('id', filter=Q(status=OfferStatus.ACCEPTED,
                                                  feedback_at__isnull=True)),
            investors=Count('investor', distinct=True),
            startups=Count('startup', distinct=True),
        )

        params = request.query_params
        queryset = everything.select_related('startup__user', 'investor')

        if params.get('holat') in OfferStatus.values:
            queryset = queryset.filter(status=params['holat'])
        if params.get('fikr') == 'bor':
            queryset = queryset.filter(feedback_at__isnull=False)
        elif params.get('fikr') == 'yoq':
            queryset = queryset.filter(status=OfferStatus.ACCEPTED, feedback_at__isnull=True)
        if params.get('natija') in OfferOutcome.values:
            queryset = queryset.filter(outcome=params['natija'])

        search = (params.get('q') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(startup__name__icontains=search) | Q(full_name__icontains=search)
                | Q(startup__full_name__icontains=search) | Q(phone__icontains=search))

        try:
            page = max(int(params.get('page', 1)), 1)
        except ValueError:
            page = 1
        count = queryset.count()
        rows = queryset[(page - 1) * self.page_size: page * self.page_size]

        return Response({
            'stats': totals,
            'count': count,
            'page': page,
            'pages': (count + self.page_size - 1) // self.page_size,
            'results': [
                {**offer_row(request, offer),
                 'owner': person(request, offer.startup.user),
                 'owner_name': offer.startup.full_name}
                for offer in rows
            ],
        })


@api_view(['DELETE'])
@permission_classes([IsPanelAdmin])
def panel_offer_delete(request, pk):
    """Nomaqbul (spam) taklifni o'chirish."""
    get_object_or_404(InvestmentOffer, pk=pk).delete()
    return Response({'deleted': pk})
