"""«Yoshlar Ovozi» — tashabbus bildirish, reyting, ovoz va takliflar."""

import random
from urllib.parse import quote

from django import forms
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Count, F, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.cabinet.models import Notification
from apps.core.constants import Region, Status

from .directions import CHEERS, DIRECTIONS, MILESTONES, get_direction
from .models import Initiative, InitiativeComment, InitiativeKind, InitiativeVote


# --------------------------------------------------------------------------
# Formalar
# --------------------------------------------------------------------------

class InitiativeForm(forms.ModelForm):
    """Tashabbus bildirish — sodda forma: kim, qaysi yo'nalish, qanday muammo."""

    class Meta:
        model = Initiative
        fields = ['direction', 'kind', 'title', 'description', 'expected_result',
                  'author_name', 'author_phone', 'region']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'voice-input',
                                            'placeholder': "Muammo yoki g'oyani bir jumlada nomlang"}),
            'description': forms.Textarea(attrs={'class': 'voice-input voice-textarea', 'rows': 6,
                                                 'placeholder': "Batafsil yozing: muammo nimada, "
                                                                "kimga tegishli, qanday hal qilinadi?"}),
            'expected_result': forms.Textarea(attrs={'class': 'voice-input voice-textarea', 'rows': 3,
                                                     'placeholder': "Hal qilinsa qanday natija bo'ladi?"}),
            'author_name': forms.TextInput(attrs={'class': 'voice-input',
                                                  'placeholder': "Familiya Ism"}),
            'author_phone': forms.TextInput(attrs={'class': 'voice-input',
                                                   'placeholder': "+998 90 123 45 67"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['direction'].widget = forms.HiddenInput()
        self.fields['kind'].widget = forms.RadioSelect(choices=InitiativeKind.choices)
        self.fields['region'].widget = forms.Select(
            attrs={'class': 'voice-input'},
            choices=[('', "Viloyatni tanlang")] + list(Region.choices),
        )
        for name in ('expected_result', 'author_phone', 'region'):
            self.fields[name].required = False

        if user is not None and user.is_authenticated and not self.is_bound:
            self.fields['author_name'].initial = user.full_name
            self.fields['author_phone'].initial = user.phone
            self.fields['region'].initial = user.region


class CommentForm(forms.ModelForm):
    """Tashabbusga taklif berish."""

    class Meta:
        model = InitiativeComment
        fields = ['author_name', 'text']
        widgets = {
            'author_name': forms.TextInput(attrs={'class': 'voice-input',
                                                  'placeholder': "Ismingiz"}),
            'text': forms.Textarea(attrs={'class': 'voice-input voice-textarea', 'rows': 3,
                                          'placeholder': "Taklifingizni yozing — qanday hal qilish "
                                                         "mumkin?"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None and user.is_authenticated and not self.is_bound:
            self.fields['author_name'].initial = user.full_name


# --------------------------------------------------------------------------
# Yordamchilar
# --------------------------------------------------------------------------

def _direction_stats():
    rows = (Initiative.objects.filter(is_published=True)
            .values('direction')
            .annotate(votes=Sum('vote_count'), ideas=Count('id')))
    return {row['direction']: {'votes': row['votes'] or 0, 'ideas': row['ideas']} for row in rows}


def _serialize_directions(stats):
    data = []
    for item in DIRECTIONS:
        row = stats.get(item['id'], {})
        data.append({
            'id': item['id'], 'scene': item['scene'], 'name': item['name'],
            'title': item['title'], 'color': item['color'], 'accent': item['accent'],
            'max': item['max'], 'unit': item['unit'], 'tagline': item['tagline'],
            'icon': item['icon'],
            'votes': row.get('votes', 0), 'ideas': row.get('ideas', 0),
        })
    return data


def _voted_ids(request, queryset):
    """Foydalanuvchi/mehmon qaysi tashabbuslarga ovoz berganini qaytaradi."""
    if not request.user.is_authenticated:
        return set()          # mehmon ovoz berolmaydi

    ids = [item.pk for item in queryset]
    if not ids:
        return set()

    votes = InitiativeVote.objects.filter(initiative_id__in=ids, user=request.user)
    return set(votes.values_list('initiative_id', flat=True))


# --------------------------------------------------------------------------
# Yoshlar tashabbuslari — reyting
# --------------------------------------------------------------------------

@ensure_csrf_cookie
def youth_view(request, direction_id=None):
    """/tashabbuslar/yoshlar/ — tashabbuslar o'rinlar bo'yicha, har birining tirik ikonkasi bilan."""
    stats = _direction_stats()
    directions = _serialize_directions(stats)

    requested = direction_id or request.GET.get('yonalish')
    active = get_direction(requested) if requested else None

    queryset = (Initiative.objects
                .filter(is_published=True, status=Status.APPROVED)
                .annotate(comment_total=Count('comments', distinct=True)))
    if active:
        queryset = queryset.filter(direction=active['id'])

    page = Paginator(queryset.order_by('-vote_count', '-created_at'), 10).get_page(
        request.GET.get('page'))
    ranking = list(page)
    voted = _voted_ids(request, ranking)

    # O'rin raqami sahifalar bo'ylab davom etadi: 2-sahifada #11, #12...
    offset = (page.number - 1) * page.paginator.per_page
    for index, item in enumerate(ranking, start=offset + 1):
        item.place = index
        item.voted = item.pk in voted
        item.direction_info = get_direction(item.direction)

    context = {
        'directions': directions,
        'active': active,
        'active_stats': stats.get(active['id']) if active else None,
        'ranking': ranking,
        'page_obj': page,
        'total_votes': sum(row['votes'] for row in stats.values()),
        'total_ideas': sum(row['ideas'] for row in stats.values()),
        'total_comments': InitiativeComment.objects.filter(is_published=True).count(),
    }
    return render(request, 'initiatives/youth_ranking.html', context)


@ensure_csrf_cookie
def initiative_detail(request, pk):
    """Bitta tashabbus: to'liq matn, tirik sahna, ovoz va takliflar."""
    initiative = get_object_or_404(
        Initiative.objects.select_related('author'), pk=pk, is_published=True,
    )
    direction = get_direction(initiative.direction)

    if request.method == 'POST' and not request.user.is_authenticated:
        messages.info(request, "Taklif berish uchun avval tizimga kiring.")
        return redirect_to_login(f"{request.path}#takliflar")

    form = CommentForm(request.POST or None, user=request.user)
    if request.method == 'POST':
        if form.is_valid():
            comment = form.save(commit=False)
            comment.initiative = initiative
            comment.author = request.user
            comment.save()

            # Muallifga bildirishnoma
            if initiative.author_id and initiative.author_id != getattr(request.user, 'pk', None):
                Notification.objects.create(
                    user=initiative.author,
                    title="Tashabbusingizga yangi taklif",
                    message=f"«{initiative.title}» — {comment.author_label}: "
                            f"{comment.text[:90]}",
                    type='info',
                    link=f"/tashabbuslar/tashabbus/{initiative.pk}/",
                )
            messages.success(request, "Taklifingiz qo'shildi. Rahmat!")
            return redirect(f"/tashabbuslar/tashabbus/{initiative.pk}/#takliflar")

    initiative.voted = initiative.pk in _voted_ids(request, [initiative])

    return render(request, 'initiatives/initiative_detail.html', {
        'initiative': initiative,
        'direction': direction,
        'rank': initiative.rank,
        'comments': initiative.comments.filter(is_published=True).select_related('author'),
        'form': form,
        'siblings': (Initiative.objects
                     .filter(direction=initiative.direction, is_published=True)
                     .exclude(pk=initiative.pk)
                     .order_by('-vote_count')[:4]),
    })


# --------------------------------------------------------------------------
# Ovoz berish
# --------------------------------------------------------------------------

@require_POST
def vote_view(request, pk):
    """Ovoz berish (AJAX) — bir kishi bir marta, faqat ro'yxatdan o'tganlar."""
    initiative = get_object_or_404(Initiative, pk=pk, is_published=True)

    if not request.user.is_authenticated:
        detail_url = reverse('initiatives:initiative_detail', args=[initiative.pk])
        return JsonResponse({
            'ok': False,
            'reason': 'auth',
            'message': "Ovoz berish uchun avval tizimga kiring.",
            'login_url': f"{reverse('accounts:login')}?next={quote(detail_url)}",
            'votes': initiative.vote_count,
        }, status=401)

    lookup = {'initiative': initiative, 'user': request.user}

    if InitiativeVote.objects.filter(**lookup).exists():
        return JsonResponse({
            'ok': False,
            'reason': 'already',
            'message': "Siz bu tashabbusga allaqachon ovoz bergansiz.",
            'votes': initiative.vote_count,
        }, status=409)

    InitiativeVote.objects.create(initiative=initiative, user=request.user, session_key='')
    Initiative.objects.filter(pk=initiative.pk).update(vote_count=F('vote_count') + 1)
    initiative.refresh_from_db(fields=['vote_count'])

    direction_votes = (Initiative.objects
                       .filter(direction=initiative.direction, is_published=True)
                       .aggregate(total=Sum('vote_count'))['total'] or 0)

    # Muallifga bildirishnoma — faqat bosqichlarda, spam bo'lmasligi uchun
    if initiative.author_id and initiative.vote_count in MILESTONES:
        Notification.objects.create(
            user=initiative.author,
            title=f"Tashabbusingiz {initiative.vote_count} ta ovoz to'pladi!",
            message=initiative.title,
            type='success',
            link=f"/tashabbuslar/tashabbus/{initiative.pk}/",
        )

    return JsonResponse({
        'ok': True,
        'votes': initiative.vote_count,
        'direction': initiative.direction,
        'direction_votes': direction_votes,
        'rank': initiative.rank,
        'message': MILESTONES.get(initiative.vote_count) or random.choice(CHEERS),
        'milestone': initiative.vote_count in MILESTONES,
    })


# --------------------------------------------------------------------------
# Tashabbus bildirish
# --------------------------------------------------------------------------

def initiative_create(request, direction_id=None):
    """Tashabbus bildirish formasi — yuborilgach reytingga tushadi."""
    direction = get_direction(direction_id or request.GET.get('yonalish') or DIRECTIONS[0]['id'])
    user = request.user if request.user.is_authenticated else None

    if request.method == 'POST':
        form = InitiativeForm(request.POST, user=user)
        if form.is_valid():
            initiative = form.save(commit=False)
            initiative.author = user
            initiative.save()
            messages.success(request, "Tashabbusingiz qabul qilindi! Endi unga ovoz berishadi.")
            return redirect(f"{_youth_url(initiative.direction)}#tashabbus-{initiative.pk}")
    else:
        form = InitiativeForm(user=user, initial={'direction': direction['id']})

    return render(request, 'initiatives/initiative_form.html', {
        'form': form,
        'direction': direction,
        'directions': DIRECTIONS,
    })


def _youth_url(direction_id):
    return f"/tashabbuslar/yoshlar/{direction_id}/"


@require_POST
def initiative_delete(request, pk):
    """Muallif o'z tashabbusini o'chiradi."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    initiative = get_object_or_404(Initiative, pk=pk, author=request.user)
    title = initiative.title
    initiative.delete()
    messages.info(request, f"«{title}» o'chirildi.")
    return redirect('cabinet:initiatives')
