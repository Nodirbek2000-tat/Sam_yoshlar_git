"""Tashabbuslarni JSON orqali ommaviy kiritish va chiqarish.

Piar uchun: loyihalar, ularning ovozlari, takliflari va mualliflari
bir faylda yuklanadi.
"""

import json

from django import forms
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.core.constants import Region, Status
from apps.initiatives.directions import DIRECTION_MAP, DIRECTIONS
from apps.initiatives.models import Initiative, InitiativeComment, InitiativeKind

from .mixins import panel_required

SAMPLE = {
    "initiatives": [
        {
            "direction": "eco",
            "kind": "idea",
            "title": "Maktablarda plastik yig'ish punktlari",
            "description": "Har bir maktabda plastik topshirish punkti bo'lsin.",
            "expected_result": "Yiliga 20 tonna plastik qayta ishlanadi.",
            "author_name": "Aziz Rahimov",
            "author_phone": "+998901112233",
            "region": "samarqand",
            "vote_count": 42,
            "created_at": "2026-08-15",
            "comments": [
                {"author_name": "Nodira Karimova",
                 "text": "Zo'r g'oya! Bizning maktabda ham qilish kerak.",
                 "created_at": "2026-08-16"}
            ],
        }
    ]
}


class ImportForm(forms.Form):
    MODE_ADD = 'add'
    MODE_REPLACE = 'replace'

    data = forms.CharField(
        label="JSON matni",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'panel-input panel-textarea',
            'rows': 14,
            'placeholder': '{"initiatives": [ ... ]}',
            'spellcheck': 'false',
        }),
    )
    file = forms.FileField(
        label="yoki JSON fayl", required=False,
        widget=forms.FileInput(attrs={'class': 'panel-file', 'accept': '.json,application/json'}),
    )
    mode = forms.ChoiceField(
        label="Rejim",
        choices=[
            (MODE_ADD, "Qo'shish — mavjudlari saqlanadi"),
            (MODE_REPLACE, "Almashtirish — avval hammasi o'chiriladi"),
        ],
        initial=MODE_ADD,
        widget=forms.RadioSelect,
    )

    def clean(self):
        cleaned = super().clean()
        raw = (cleaned.get('data') or '').strip()
        uploaded = cleaned.get('file')

        if uploaded:
            try:
                raw = uploaded.read().decode('utf-8')
            except UnicodeDecodeError:
                raise forms.ValidationError("Fayl UTF-8 kodlashida bo'lishi kerak.")

        if not raw:
            raise forms.ValidationError("JSON matnini kiriting yoki fayl yuklang.")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise forms.ValidationError(f"JSON xato: {error}")

        if isinstance(payload, dict):
            items = payload.get('initiatives') or payload.get('tashabbuslar')
        else:
            items = payload

        if not isinstance(items, list):
            raise forms.ValidationError(
                "JSON ichida `initiatives` ro'yxati bo'lishi kerak (yoki to'g'ridan-to'g'ri ro'yxat)."
            )

        cleaned['items'] = items
        return cleaned


def _parse_when(value):
    """Sana yoki sana-vaqtni o'qiydi; bo'lmasa None."""
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed:
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    day = parse_date(str(value))
    if day:
        return timezone.make_aware(
            timezone.datetime(day.year, day.month, day.day, 12, 0)
        )
    return None


def _import_items(items, mode):
    """Ro'yxatni bazaga yozadi. (natija, xatolar) qaytaradi."""
    errors = []
    created_initiatives = 0
    created_comments = 0
    total_votes = 0

    if mode == ImportForm.MODE_REPLACE:
        Initiative.objects.all().delete()

    valid_regions = set(Region.values)
    valid_kinds = set(InitiativeKind.values)

    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            errors.append(f"#{index}: obyekt emas — o'tkazib yuborildi")
            continue

        title = (raw.get('title') or '').strip()
        description = (raw.get('description') or '').strip()
        direction = (raw.get('direction') or '').strip()

        if not title:
            errors.append(f"#{index}: `title` yo'q")
            continue
        if not description:
            errors.append(f"#{index}: «{title[:30]}» — `description` yo'q")
            continue
        if direction not in DIRECTION_MAP:
            errors.append(f"#{index}: «{title[:30]}» — noma'lum yo'nalish `{direction}`")
            continue

        kind = (raw.get('kind') or 'idea').strip()
        if kind not in valid_kinds:
            kind = InitiativeKind.IDEA

        region = (raw.get('region') or '').strip()
        if region not in valid_regions:
            region = ''

        try:
            vote_count = max(int(raw.get('vote_count') or 0), 0)
        except (TypeError, ValueError):
            vote_count = 0

        initiative = Initiative.objects.create(
            direction=direction,
            kind=kind,
            title=title[:200],
            summary=(raw.get('summary') or description)[:300],
            description=description,
            expected_result=(raw.get('expected_result') or '')[:2000],
            author_name=(raw.get('author_name') or "Anonim")[:150],
            author_phone=(raw.get('author_phone') or '')[:25],
            author_email=(raw.get('author_email') or '')[:254],
            region=region,
            vote_count=vote_count,
            status=Status.APPROVED,
            is_published=bool(raw.get('is_published', True)),
        )

        created_at = _parse_when(raw.get('created_at'))
        if created_at:
            Initiative.objects.filter(pk=initiative.pk).update(created_at=created_at)

        created_initiatives += 1
        total_votes += vote_count

        for raw_comment in raw.get('comments') or []:
            if not isinstance(raw_comment, dict):
                continue
            text = (raw_comment.get('text') or '').strip()
            if not text:
                continue

            comment = InitiativeComment.objects.create(
                initiative=initiative,
                author_name=(raw_comment.get('author_name') or "Anonim")[:150],
                text=text,
            )
            comment_at = _parse_when(raw_comment.get('created_at'))
            if comment_at:
                InitiativeComment.objects.filter(pk=comment.pk).update(created_at=comment_at)
            created_comments += 1

    return {
        'initiatives': created_initiatives,
        'comments': created_comments,
        'votes': total_votes,
    }, errors


@panel_required
def import_view(request):
    """JSON import sahifasi."""
    form = ImportForm(request.POST or None, request.FILES or None)
    result = None
    errors = []

    if request.method == 'POST' and form.is_valid():
        result, errors = _import_items(form.cleaned_data['items'], form.cleaned_data['mode'])

        if result['initiatives']:
            messages.success(
                request,
                f"{result['initiatives']} ta tashabbus, {result['comments']} ta taklif "
                f"va {result['votes']} ta ovoz kiritildi."
            )
        else:
            messages.warning(request, "Hech narsa kiritilmadi — xatolarni tekshiring.")

    return render(request, 'panel/import.html', {
        'form': form,
        'result': result,
        'errors': errors,
        'sample': json.dumps(SAMPLE, ensure_ascii=False, indent=2),
        'directions': DIRECTIONS,
        'kinds': InitiativeKind.choices,
        'total': Initiative.objects.count(),
        'active': 'import',
    })


@panel_required
def export_view(request):
    """Mavjud tashabbuslarni JSON qilib beradi — tahrirlab qayta yuklash uchun."""
    items = []
    queryset = (Initiative.objects.prefetch_related('comments').order_by('direction',
                                                                        '-vote_count'))
    for initiative in queryset:
        items.append({
            'direction': initiative.direction,
            'kind': initiative.kind,
            'title': initiative.title,
            'summary': initiative.summary,
            'description': initiative.description,
            'expected_result': initiative.expected_result,
            'author_name': initiative.author_name,
            'author_phone': initiative.author_phone,
            'region': initiative.region,
            'vote_count': initiative.vote_count,
            'is_published': initiative.is_published,
            'created_at': initiative.created_at.isoformat(),
            'comments': [
                {
                    'author_name': comment.author_name,
                    'text': comment.text,
                    'created_at': comment.created_at.isoformat(),
                }
                for comment in initiative.comments.all()
            ],
        })

    response = JsonResponse({'initiatives': items}, json_dumps_params={
        'ensure_ascii': False, 'indent': 2,
    })
    stamp = timezone.localdate().isoformat()
    response['Content-Disposition'] = f'attachment; filename="tashabbuslar-{stamp}.json"'
    return response
