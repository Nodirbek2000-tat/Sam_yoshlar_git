"""Kirish — JWT qaytaradi. Ikki yo'l bor.

**Telegram kodi** — hamma uchun, ro'yxatdan o'tishning yagona yo'li:
  1. Foydalanuvchi botga `/start` yozadi va raqamini ulashadi
  2. Bot 6 xonali kod beradi
  3. Frontend shu kodni `/api/v1/auth/telegram/` ga yuboradi

**Login va parol** — faqat biz qo'lda ochib beradigan hisoblar uchun
(tashkilotlar va adminlar). Telegram orqali kelgan foydalanuvchida parol
o'rnatilmagan, shuning uchun bu yo'l ular uchun yopiq.
"""
from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import TelegramAuthCode

from .onboarding import onboarding_step
from .serializers import ProfileUpdateSerializer, UserSerializer


class LoginThrottle(AnonRateThrottle):
    """Parol tanlashga urinishni cheklaydi."""

    scope = 'login'


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


@api_view(['GET'])
@permission_classes([AllowAny])
def auth_info(request):
    """Kirish sahifasi uchun: bot manzili."""
    username = getattr(settings, 'TELEGRAM_BOT_USERNAME', '') or 'yoshtadbirkorlarbot'
    return Response({
        'bot_username': username,
        'bot_url': f"https://t.me/{username}",
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def password_login(request):
    """Login va parol bilan kirish — tashkilot va admin hisoblari uchun.

    Telegram orqali kelgan foydalanuvchida parol o'rnatilmagan
    (`set_unusable_password`), shuning uchun ular bu yerdan kira olmaydi —
    xato xabari esa ikkala holatda bir xil, hisob bor-yo'qligini oshkor qilmaydi.
    """
    email = str(request.data.get('email', '')).strip().lower()
    password = str(request.data.get('password', ''))

    if not email or not password:
        return Response({'detail': "Login va parolni kiriting."},
                        status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(request, username=email, password=password)

    if user is None or not user.is_active:
        return Response({'detail': "Login yoki parol noto'g'ri."},
                        status=status.HTTP_401_UNAUTHORIZED)

    # Tashkilot va admin uchun odatda `None`; boshqa rol parol bilan kirsa
    # ham qolgan qadamga yuboriladi
    step = onboarding_step(user)

    return Response({
        **tokens_for(user),
        'user': UserSerializer(user, context={'request': request}).data,
        'needs_profile': step is not None,
        'onboarding': step,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def telegram_login(request):
    """Bot bergan kodni tokenga almashtiradi."""
    code = str(request.data.get('code', '')).strip().replace(' ', '')

    if not code:
        return Response({'detail': "Kodni kiriting."},
                        status=status.HTTP_400_BAD_REQUEST)
    if not code.isdigit():
        return Response({'detail': "Kod faqat raqamlardan iborat bo'ladi."},
                        status=status.HTTP_400_BAD_REQUEST)

    entry = TelegramAuthCode.objects.select_related('user').filter(code=code).first()

    if entry is None:
        return Response({'detail': "Bunday kod topilmadi. Botdan yangi kod oling."},
                        status=status.HTTP_400_BAD_REQUEST)
    if entry.used_at is not None:
        return Response({'detail': "Bu kod allaqachon ishlatilgan. Yangi kod oling."},
                        status=status.HTTP_400_BAD_REQUEST)
    if entry.is_expired:
        return Response({'detail': "Kod eskirgan. Botdan yangi kod oling."},
                        status=status.HTTP_400_BAD_REQUEST)

    from apps.accounts.models import AGE_LIMIT
    from apps.accounts.telegram_views import is_age_exempt

    # Bot yosh katta bo'lsa kod bermaydi; bu — eski kod bilan kirib qolmasin
    if not is_age_exempt(entry.user) and (entry.user.age or 0) > AGE_LIMIT:
        return Response({'detail': f"Bu saytga faqat {AGE_LIMIT} yoshgacha bo'lgan yoshlar kira oladi."},
                        status=status.HTTP_403_FORBIDDEN)

    entry.used_at = timezone.now()
    entry.save(update_fields=['used_at'])

    user = entry.user
    # Rol tanlanmagan yoki biznes/startap ma'lumoti berilmagan bo'lsa —
    # front foydalanuvchini o'sha qadamga yuboradi
    step = onboarding_step(user)

    return Response({
        **tokens_for(user),
        'user': UserSerializer(user, context={'request': request}).data,
        'needs_profile': step is not None,
        'onboarding': step,
    })


class Me(RetrieveUpdateAPIView):
    """Joriy foydalanuvchi: ko'rish va profilni to'ldirish (rol tanlash ham shu yerda)."""

    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        return (ProfileUpdateSerializer if self.request.method in ('PUT', 'PATCH')
                else UserSerializer)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        user = self.get_object()

        # «O'zbekistonda o'qiyman» — chet eldagi tengdoshlar ro'yxatidan yashiriladi
        if user.study_location == 'uz':
            from apps.abroad.models import Peer
            Peer.objects.filter(user=user, is_published=True).update(is_published=False)

        # Rol tanlangach hisob to'liq hisoblanadi
        if not user.is_verified:
            user.is_verified = True
            user.save(update_fields=['is_verified'])

        response.data = UserSerializer(user, context={'request': request}).data
        return response
