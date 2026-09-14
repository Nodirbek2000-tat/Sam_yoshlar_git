"""Telegram bot orqali ro'yxatdan o'tish va kirish — yagona usul.

Oqim:
  1. Foydalanuvchi botga o'tadi va raqamini yuboradi.
  2. Bot Django'ga ma'lumotlarni yuboradi -> Django hisob ochadi va 6 xonali kod qaytaradi.
  3. Bot kodni ko'rsatadi.
  4. Foydalanuvchi kodni saytga kiritadi -> tizimga kiradi.
"""

import hmac
import json
import random

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import AGE_LIMIT, Role, TelegramAuthCode

User = get_user_model()


def _bot_username():
    return getattr(settings, 'TELEGRAM_BOT_USERNAME', 'yoshtadbirkorlarbot')


def _api_secret():
    return getattr(settings, 'TELEGRAM_API_SECRET', '')


class CodeForm(forms.Form):
    code = forms.CharField(
        label="Bot bergan kod",
        max_length=8,
        widget=forms.TextInput(attrs={
            'class': 'tg-code-input',
            'placeholder': '000000',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
            'autofocus': True,
        }),
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip().replace(' ', '')
        if not code.isdigit():
            raise forms.ValidationError("Kod faqat raqamlardan iborat bo'ladi.")

        entry = TelegramAuthCode.objects.select_related('user').filter(code=code).first()
        if entry is None:
            raise forms.ValidationError("Bunday kod topilmadi. Botdan yangi kod oling.")
        if entry.used_at is not None:
            raise forms.ValidationError("Bu kod allaqachon ishlatilgan. Yangi kod oling.")
        if entry.is_expired:
            raise forms.ValidationError("Kod eskirgan. Botdan yangi kod oling.")

        self.entry = entry
        return code


def telegram_login(request):
    """Yagona kirish sahifasi: botga o'tish + kod kiritish."""
    if request.user.is_authenticated:
        return redirect('cabinet:dashboard')

    form = CodeForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        entry = form.entry
        entry.used_at = timezone.now()
        entry.save(update_fields=['used_at'])

        login(request, entry.user, backend='apps.accounts.backends.EmailOrPhoneBackend')
        messages.success(request, f"Xush kelibsiz, {entry.user.get_short_name()}!")
        return redirect(request.GET.get('next') or 'cabinet:dashboard')

    return render(request, 'accounts/telegram_login.html', {
        'form': form,
        'bot_username': _bot_username(),
        'bot_link': f"https://t.me/{_bot_username()}",
    })


@csrf_exempt
@require_POST
def telegram_issue_code(request):
    """Bot chaqiradi: foydalanuvchi ma'lumotlari -> hisob + kod.

    Kutiladi: telegram_id, first_name, last_name, username
    Ixtiyoriy: phone (birinchi marta majburiy), age, photo (fayl)

    Kod berilmasa `ok: false` va bot nima so'rashi kerakligi qaytadi:
    `need_phone`, `need_age`, `age_limit` (AGE_LIMIT dan katta), `bad_age`.
    """
    secret = _api_secret()
    provided = request.headers.get('X-Bot-Secret', '')
    if not secret or not hmac.compare_digest(provided, secret):
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    data, photo = _read_payload(request)
    if data is None:
        return JsonResponse({'ok': False, 'error': 'bad_payload'}, status=400)

    telegram_id = data.get('telegram_id')
    if not telegram_id:
        return JsonResponse({'ok': False, 'error': 'missing_telegram_id'}, status=400)

    age, age_error = _parse_age(data.get('age'))
    if age_error:
        return JsonResponse({'ok': False, 'error': 'bad_age'})

    phone = normalize_phone(data.get('phone'))
    username = (data.get('username') or '').strip().lstrip('@')

    # Raqam faqat birinchi marta so'raladi: hisob bo'lsa, u telegram_id bo'yicha topiladi
    if not phone and not User.objects.filter(telegram_id=int(telegram_id)).exists():
        return JsonResponse({'ok': False, 'error': 'need_phone'})

    user, created = _get_or_create_user(
        telegram_id=int(telegram_id),
        first_name=(data.get('first_name') or '').strip(),
        last_name=(data.get('last_name') or '').strip(),
        username=username,
        phone=phone,
    )

    if photo and not user.avatar:
        user.avatar.save(f"tg_{telegram_id}.jpg", ContentFile(photo.read()), save=True)

    if age is not None and user.age != age:
        user.age = age
        user.save(update_fields=['age'])

    # Adminlar va tashkilotlarning hisobini biz ochamiz — ulardan yosh so'ralmaydi
    if not is_age_exempt(user):
        if user.age is None:
            return JsonResponse({'ok': False, 'error': 'need_age', 'created': created})
        if user.age > AGE_LIMIT:
            return JsonResponse({'ok': False, 'error': 'age_limit', 'limit': AGE_LIMIT})

    # Eski kodlarni bekor qilamiz — bir vaqtda bitta amaldagi kod bo'lsin
    TelegramAuthCode.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    entry = TelegramAuthCode.objects.create(
        code=_generate_code(),
        user=user,
        telegram_id=int(telegram_id),
    )

    return JsonResponse({
        'ok': True,
        'code': entry.code,
        'created': created,
        'name': user.full_name,
    })


def is_age_exempt(user):
    return user.is_superuser or user.is_staff or user.role in (Role.ADMIN, Role.ORGANIZATION)


def _parse_age(raw):
    """(yosh, xato) — yosh berilmagan bo'lsa (None, False)."""
    if raw in (None, ''):
        return None, False
    try:
        age = int(str(raw).strip())
    except ValueError:
        return None, True
    if not 7 <= age <= 100:
        return None, True
    return age, False


def _read_payload(request):
    """Bot JSON, form yoki multipart yuborishi mumkin — hammasini qabul qilamiz."""
    content_type = (request.content_type or '').lower()

    if content_type.startswith('multipart') or \
       content_type.startswith('application/x-www-form-urlencoded'):
        return request.POST, request.FILES.get('photo')

    try:
        return json.loads(request.body or '{}'), None
    except json.JSONDecodeError:
        return None, None


def normalize_phone(phone):
    """Raqamni yagona ko'rinishga keltiradi.

    Telegram ba'zan `+` bilan, ba'zan `+` siz yuboradi; foydalanuvchi esa
    bo'shliq va tire bilan yozgan bo'lishi mumkin.
    +998 50 005-68-21  ->  +998500056821
    998500056821       ->  +998500056821
    """
    digits = ''.join(ch for ch in str(phone or '') if ch.isdigit())
    return f"+{digits}" if digits else ''


def _find_by_phone(phone):
    """Raqam bo'yicha hisobni topadi — yozilish ko'rinishiga qaramay."""
    if not phone:
        return None

    exact = User.objects.filter(phone=phone).first()
    if exact:
        return exact

    # Bazadagi raqamlar turlicha yozilgan bo'lishi mumkin — oxirgi 9 raqam bo'yicha solishtiramiz
    tail = phone[-9:]
    if len(tail) < 9:
        return None

    for candidate in User.objects.exclude(phone='').only('id', 'phone'):
        if normalize_phone(candidate.phone).endswith(tail):
            return candidate
    return None


def _generate_code():
    """Takrorlanmaydigan 6 xonali kod."""
    for _ in range(50):
        code = f"{random.randint(0, 999999):06d}"
        if not TelegramAuthCode.objects.filter(code=code).exists():
            return code
    # Deyarli imkonsiz, lekin baribir zaxira
    return f"{random.randint(1000000, 9999999)}"


def _get_or_create_user(telegram_id, first_name, last_name, username, phone):
    """Telegram ID bo'yicha hisobni topadi yoki ochadi (parolsiz).

    Ro'yxatdan o'tishda faqat Telegram bergan ma'lumot olinadi —
    qolgani keyin kabinetda to'ldiriladi.
    """
    user = User.objects.filter(telegram_id=telegram_id).first()
    if user:
        changed = []
        if phone and user.phone != phone:
            user.phone = phone
            changed.append('phone')
        if username and user.telegram_username != username:
            user.telegram_username = username
            changed.append('telegram_username')
        if changed:
            user.save(update_fields=changed)
        return user, False

    if phone:
        existing = _find_by_phone(phone)
        if existing:
            existing.telegram_id = telegram_id
            existing.telegram_username = username
            existing.is_verified = True
            existing.save(update_fields=['telegram_id', 'telegram_username', 'is_verified'])
            return existing, False

    full_name = f"{first_name} {last_name}".strip() or username or f"Foydalanuvchi {telegram_id}"

    user = User.objects.create_user(
        email=f"tg{telegram_id}@telegram.local",
        password=None,
        full_name=full_name,
        phone=phone,
        telegram_id=telegram_id,
        telegram_username=username,
        is_verified=True,
    )
    user.set_unusable_password()
    user.save(update_fields=['password'])
    return user, True
