from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.abroad.models import Peer
from apps.business.models import BusinessProfile
from apps.cabinet.models import Appeal, Notification, Suggestion
from apps.content.models import Announcement, Event, EventRegistration, News
from apps.core.constants import Status
from apps.core.models import Leader, SiteSetting, Task
from apps.initiatives.directions import DIRECTIONS
from apps.initiatives.models import (Initiative, InitiativeComment, InitiativeVote,
                                     Organization, Problem, Solution)
from apps.startups.models import Startup

from .forms import (AnnouncementForm, AppealResponseForm, EventForm, LeaderForm, NewsForm,
                    SiteSettingForm, TaskForm, UserForm)
from .mixins import is_panel_admin, panel_required

User = get_user_model()

PAGE_SIZE = 15


def _paginate(request, queryset, per_page=PAGE_SIZE):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


# ---------------------------------------------------------------- Dashboard

@panel_required
def dashboard(request):
    now = timezone.now()
    week_ago = now - timezone.timedelta(days=7)

    stats = [
        {'icon': '👥', 'label': "Foydalanuvchilar", 'value': User.objects.count(),
         'sub': f"+{User.objects.filter(date_joined__gte=week_ago).count()} bu hafta",
         'url': 'panel:users', 'tone': 'primary'},
        {'icon': '📰', 'label': "Yangiliklar", 'value': News.objects.count(),
         'sub': f"{News.objects.filter(is_published=True).count()} ta chop etilgan",
         'url': 'panel:news', 'tone': 'info'},
        {'icon': '📅', 'label': "Tadbirlar", 'value': Event.objects.count(),
         'sub': f"{Event.objects.filter(starts_at__gte=now).count()} ta kelasi",
         'url': 'panel:events', 'tone': 'success'},
        {'icon': '📢', 'label': "E'lonlar", 'value': Announcement.objects.count(),
         'sub': f"{Announcement.objects.filter(is_active=True).count()} ta faol",
         'url': 'panel:announcements', 'tone': 'accent'},
    ]

    pending = [
        {'icon': '📨', 'label': "Javob kutayotgan murojaatlar",
         'value': Appeal.objects.filter(status=Status.PENDING).count(), 'url': 'panel:appeals'},
        {'icon': '💡', 'label': "Ko'rilmagan takliflar",
         'value': Suggestion.objects.filter(status=Status.PENDING).count(),
         'url': 'panel:suggestions'},
        {'icon': '🚀', 'label': "Tasdiq kutayotgan StartUplar",
         'value': Startup.objects.filter(status=Status.PENDING).count(), 'url': 'panel:startups'},
        {'icon': '🌟', 'label': "Yangi yechimlar",
         'value': Solution.objects.filter(status=Status.PENDING).count(),
         'url': 'panel:solutions'},
    ]

    context = {
        'stats': stats,
        'pending': pending,
        'recent_users': User.objects.order_by('-date_joined')[:6],
        'recent_appeals': Appeal.objects.select_related('user')[:6],
        'upcoming_events': (Event.objects.filter(starts_at__gte=now)
                            .annotate(reg_count=Count('registrations',
                                                      filter=Q(registrations__is_cancelled=False)))
                            .order_by('starts_at')[:5]),
        'active': 'dashboard',
    }
    return render(request, 'panel/dashboard.html', context)


# ---------------------------------------------------------------- Yangiliklar

@panel_required
def news_list(request):
    queryset = News.objects.all()
    search = request.GET.get('q', '').strip()
    if search:
        queryset = queryset.filter(title__icontains=search)
    return render(request, 'panel/news_list.html', {
        'page_obj': _paginate(request, queryset),
        'search': search,
        'active': 'news',
    })


@panel_required
def news_form(request, pk=None):
    instance = get_object_or_404(News, pk=pk) if pk else None
    form = NewsForm(request.POST or None, request.FILES or None, instance=instance)

    if request.method == 'POST' and form.is_valid():
        news = form.save(commit=False)
        if news.author_id is None:
            news.author = request.user
        news.save()
        messages.success(request, "Yangilik saqlandi." if instance else "Yangilik qo'shildi.")
        return redirect('panel:news')

    return render(request, 'panel/form.html', {
        'form': form,
        'object': instance,
        'title': "Yangilikni tahrirlash" if instance else "Yangi yangilik",
        'subtitle': "Sarlavha, kategoriya, rasm va matnni to'ldiring",
        'back_url': 'panel:news',
        'delete_url': 'panel:news_delete',
        'active': 'news',
    })


@panel_required
@require_POST
def news_delete(request, pk):
    get_object_or_404(News, pk=pk).delete()
    messages.info(request, "Yangilik o'chirildi.")
    return redirect('panel:news')


# ---------------------------------------------------------------- Tadbirlar

@panel_required
def event_list(request):
    queryset = (Event.objects.annotate(
        reg_count=Count('registrations', filter=Q(registrations__is_cancelled=False)))
        .order_by('-starts_at'))
    search = request.GET.get('q', '').strip()
    if search:
        queryset = queryset.filter(title__icontains=search)
    return render(request, 'panel/event_list.html', {
        'page_obj': _paginate(request, queryset),
        'search': search,
        'active': 'events',
    })


@panel_required
def event_form(request, pk=None):
    instance = get_object_or_404(Event, pk=pk) if pk else None
    form = EventForm(request.POST or None, request.FILES or None, instance=instance)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Tadbir saqlandi." if instance else "Tadbir qo'shildi.")
        return redirect('panel:events')

    return render(request, 'panel/form.html', {
        'form': form,
        'object': instance,
        'title': "Tadbirni tahrirlash" if instance else "Yangi tadbir",
        'subtitle': "Sana, manzil va ishtirokchilar limitini belgilang",
        'back_url': 'panel:events',
        'delete_url': 'panel:event_delete',
        'extra_link': ('panel:event_registrations', instance.pk, "Ishtirokchilar") if instance else None,
        'active': 'events',
    })


@panel_required
@require_POST
def event_delete(request, pk):
    get_object_or_404(Event, pk=pk).delete()
    messages.info(request, "Tadbir o'chirildi.")
    return redirect('panel:events')


@panel_required
def event_registrations(request, pk):
    event = get_object_or_404(Event, pk=pk)
    registrations = event.registrations.select_related('user').order_by('-created_at')
    return render(request, 'panel/event_registrations.html', {
        'event': event,
        'registrations': registrations,
        'active': 'events',
    })


@panel_required
@require_POST
def toggle_attendance(request, pk):
    registration = get_object_or_404(EventRegistration, pk=pk)
    registration.attended = not registration.attended
    registration.save(update_fields=['attended', 'updated_at'])
    return redirect('panel:event_registrations', pk=registration.event_id)


# ---------------------------------------------------------------- E'lonlar

@panel_required
def announcement_list(request):
    queryset = Announcement.objects.all()
    search = request.GET.get('q', '').strip()
    if search:
        queryset = queryset.filter(title__icontains=search)
    return render(request, 'panel/announcement_list.html', {
        'page_obj': _paginate(request, queryset),
        'search': search,
        'active': 'announcements',
    })


@panel_required
def announcement_form(request, pk=None):
    instance = get_object_or_404(Announcement, pk=pk) if pk else None
    form = AnnouncementForm(request.POST or None, request.FILES or None, instance=instance)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "E'lon saqlandi." if instance else "E'lon qo'shildi.")
        return redirect('panel:announcements')

    return render(request, 'panel/form.html', {
        'form': form,
        'object': instance,
        'title': "E'lonni tahrirlash" if instance else "Yangi e'lon",
        'subtitle': "Grant, kredit, tanlov yoki vakansiya e'loni",
        'back_url': 'panel:announcements',
        'delete_url': 'panel:announcement_delete',
        'active': 'announcements',
    })


@panel_required
@require_POST
def announcement_delete(request, pk):
    get_object_or_404(Announcement, pk=pk).delete()
    messages.info(request, "E'lon o'chirildi.")
    return redirect('panel:announcements')


# ---------------------------------------------------------------- Foydalanuvchilar

@panel_required
def user_list(request):
    queryset = User.objects.all()

    search = request.GET.get('q', '').strip()
    if search:
        queryset = queryset.filter(
            Q(full_name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
        )

    role = request.GET.get('rol')
    if role:
        queryset = queryset.filter(role=role)

    status = request.GET.get('holat')
    if status == 'tasdiqlangan':
        queryset = queryset.filter(is_verified=True)
    elif status == 'kutilmoqda':
        queryset = queryset.filter(is_verified=False)
    elif status == 'bloklangan':
        queryset = queryset.filter(is_active=False)

    from apps.accounts.models import Role
    return render(request, 'panel/user_list.html', {
        'page_obj': _paginate(request, queryset),
        'search': search,
        'roles': Role.choices,
        'active_role': role or '',
        'active_status': status or '',
        'active': 'users',
    })


@panel_required
def user_detail(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=user_obj)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"{user_obj.full_name} ma'lumotlari saqlandi.")
        return redirect('panel:user_detail', pk=pk)

    return render(request, 'panel/user_detail.html', {
        'user_obj': user_obj,
        'form': form,
        'business': BusinessProfile.objects.filter(user=user_obj).first(),
        'appeals': user_obj.appeals.all()[:5],
        'startups': Startup.objects.filter(user=user_obj)[:5],
        'registrations': user_obj.event_registrations.select_related('event')[:5],
        'active': 'users',
    })


@panel_required
@require_POST
def user_toggle(request, pk, action):
    user_obj = get_object_or_404(User, pk=pk)

    if user_obj == request.user:
        messages.error(request, "O'z hisobingizni o'zgartira olmaysiz.")
        return redirect('panel:user_detail', pk=pk)

    if action == 'admin':
        # Bitta tugma bilan adminlik berish / olib qo'yish
        making_admin = not is_panel_admin(user_obj)
        if making_admin:
            user_obj.is_staff = True
            user_obj.is_verified = True
            user_obj.role = 'admin'
            state = "administrator qilindi"
        else:
            user_obj.is_staff = False
            user_obj.role = 'entrepreneur'
            state = "adminlikdan olindi"
        user_obj.save(update_fields=['is_staff', 'is_verified', 'role'])

        Notification.objects.create(
            user=user_obj,
            title="Sizga administrator huquqi berildi" if making_admin
                  else "Administrator huquqi olib qo'yildi",
            message="Endi boshqaruv paneliga kira olasiz." if making_admin
                    else "Boshqaruv paneliga kirish yopildi.",
            type='success' if making_admin else 'warning',
        )
    elif action == 'verify':
        user_obj.is_verified = not user_obj.is_verified
        user_obj.save(update_fields=['is_verified'])
        state = "tasdiqlandi" if user_obj.is_verified else "tasdiqdan olindi"
        Notification.objects.create(
            user=user_obj,
            title="Hisobingiz tasdiqlandi" if user_obj.is_verified else "Hisob tasdig'i olindi",
            message="Endi platformaning barcha imkoniyatlaridan foydalanishingiz mumkin."
                    if user_obj.is_verified else "Savollar bo'lsa kengashga murojaat qiling.",
            type='success' if user_obj.is_verified else 'warning',
        )
    elif action == 'block':
        user_obj.is_active = not user_obj.is_active
        user_obj.save(update_fields=['is_active'])
        state = "faollashtirildi" if user_obj.is_active else "bloklandi"
    else:
        raise ValueError(f"Noma'lum amal: {action}")

    messages.success(request, f"{user_obj.full_name} {state}.")
    return redirect('panel:user_detail', pk=pk)


# ---------------------------------------------------------------- Murojaat / taklif

@panel_required
def appeal_list(request):
    queryset = Appeal.objects.select_related('user')
    status = request.GET.get('holat')
    if status in Status.values:
        queryset = queryset.filter(status=status)
    return render(request, 'panel/appeal_list.html', {
        'page_obj': _paginate(request, queryset),
        'statuses': Status.choices,
        'active_status': status or '',
        'active': 'appeals',
    })


@panel_required
def appeal_detail(request, pk):
    appeal = get_object_or_404(Appeal.objects.select_related('user'), pk=pk)
    form = AppealResponseForm(request.POST or None, initial={
        'status': appeal.status, 'response': appeal.response,
    })

    if request.method == 'POST' and form.is_valid():
        appeal.status = form.cleaned_data['status']
        appeal.response = form.cleaned_data['response']
        if appeal.response and not appeal.responded_at:
            appeal.responded_at = timezone.now()
            appeal.responded_by = request.user
        appeal.save()

        if appeal.response:
            Notification.objects.create(
                user=appeal.user,
                title="Murojaatingizga javob berildi",
                message=appeal.subject,
                type='success',
                link='/kabinet/murojaatlar/',
            )
        messages.success(request, "Murojaat yangilandi.")
        return redirect('panel:appeals')

    return render(request, 'panel/appeal_detail.html', {
        'appeal': appeal, 'form': form, 'active': 'appeals',
    })


@panel_required
def suggestion_list(request):
    queryset = Suggestion.objects.select_related('user')
    return render(request, 'panel/suggestion_list.html', {
        'page_obj': _paginate(request, queryset),
        'statuses': Status.choices,
        'active': 'suggestions',
    })


@panel_required
@require_POST
def suggestion_status(request, pk):
    suggestion = get_object_or_404(Suggestion, pk=pk)
    new_status = request.POST.get('status')
    if new_status in Status.values:
        suggestion.status = new_status
        suggestion.save(update_fields=['status', 'updated_at'])
        messages.success(request, "Taklif holati yangilandi.")
    return redirect('panel:suggestions')


# ---------------------------------------------------------------- StartUp / Tashabbus

@panel_required
def startup_list(request):
    queryset = Startup.objects.all()
    status = request.GET.get('holat')
    if status in Status.values:
        queryset = queryset.filter(status=status)
    return render(request, 'panel/startup_list.html', {
        'page_obj': _paginate(request, queryset),
        'statuses': Status.choices,
        'active_status': status or '',
        'active': 'startups',
    })


@panel_required
@require_POST
def startup_status(request, pk):
    startup = get_object_or_404(Startup, pk=pk)
    new_status = request.POST.get('status')
    if new_status in Status.values:
        startup.status = new_status
        startup.save(update_fields=['status', 'updated_at'])
        if startup.user_id:
            Notification.objects.create(
                user=startup.user,
                title=f"StartUp holati: {startup.get_status_display()}",
                message=startup.name,
                type='success' if new_status == Status.APPROVED else 'info',
            )
        messages.success(request, "StartUp holati yangilandi.")
    return redirect('panel:startups')


@panel_required
def problem_list(request):
    queryset = (Problem.objects.select_related('organization')
                .annotate(solution_count=Count('solutions'))
                .order_by('-created_at'))
    return render(request, 'panel/problem_list.html', {
        'page_obj': _paginate(request, queryset),
        'organizations': Organization.objects.count(),
        'active': 'problems',
    })


@panel_required
def solution_list(request):
    queryset = Solution.objects.select_related('problem', 'problem__organization')
    status = request.GET.get('holat')
    if status in Status.values:
        queryset = queryset.filter(status=status)
    return render(request, 'panel/solution_list.html', {
        'page_obj': _paginate(request, queryset),
        'statuses': Status.choices,
        'active_status': status or '',
        'active': 'solutions',
    })


@panel_required
@require_POST
def solution_status(request, pk):
    solution = get_object_or_404(Solution, pk=pk)
    new_status = request.POST.get('status')
    if new_status in Status.values:
        solution.status = new_status
        solution.save(update_fields=['status', 'updated_at'])
        messages.success(request, "Yechim holati yangilandi.")
    return redirect('panel:solutions')


# ---------------------------------------------------------------- Sayt sozlamalari

@panel_required
def settings_view(request):
    site = SiteSetting.load()
    form = SiteSettingForm(request.POST or None, request.FILES or None, instance=site)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Sayt sozlamalari saqlandi.")
        return redirect('panel:settings')

    return render(request, 'panel/settings.html', {
        'form': form,
        'leaders': Leader.objects.all(),
        'tasks': Task.objects.all(),
        'active': 'settings',
    })


@panel_required
def leader_form(request, pk=None):
    instance = get_object_or_404(Leader, pk=pk) if pk else None
    form = LeaderForm(request.POST or None, request.FILES or None, instance=instance)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Saqlandi.")
        return redirect('panel:settings')

    return render(request, 'panel/form.html', {
        'form': form,
        'object': instance,
        'title': "Rahbar / a'zoni tahrirlash" if instance else "Yangi rahbar / a'zo",
        'subtitle': "Kengash haqida sahifasida ko'rinadi",
        'back_url': 'panel:settings',
        'delete_url': 'panel:leader_delete',
        'active': 'settings',
    })


@panel_required
@require_POST
def leader_delete(request, pk):
    get_object_or_404(Leader, pk=pk).delete()
    messages.info(request, "O'chirildi.")
    return redirect('panel:settings')


@panel_required
def task_form(request, pk=None):
    instance = get_object_or_404(Task, pk=pk) if pk else None
    form = TaskForm(request.POST or None, instance=instance)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Saqlandi.")
        return redirect('panel:settings')

    return render(request, 'panel/form.html', {
        'form': form,
        'object': instance,
        'title': "Vazifani tahrirlash" if instance else "Yangi vazifa",
        'subtitle': "Kengash vazifalari ro'yxati",
        'back_url': 'panel:settings',
        'delete_url': 'panel:task_delete',
        'active': 'settings',
    })


@panel_required
@require_POST
def task_delete(request, pk):
    get_object_or_404(Task, pk=pk).delete()
    messages.info(request, "O'chirildi.")
    return redirect('panel:settings')


# ---------------------------------------------------------------- Yoshlar Ovozi

@panel_required
def voice_overview(request):
    """Yo'nalishlar kesimida reyting: qaysi yo'nalish qancha ovoz yig'gan."""
    rows = (Initiative.objects.filter(is_published=True)
            .values('direction')
            .annotate(votes=Sum('vote_count'), ideas=Count('id')))
    stats = {row['direction']: row for row in rows}

    directions = []
    for item in DIRECTIONS:
        row = stats.get(item['id'], {})
        votes = row.get('votes') or 0
        directions.append({
            'id': item['id'], 'name': item['name'], 'title': item['title'],
            'color': item['color'], 'max': item['max'], 'unit': item['unit'],
            'votes': votes, 'ideas': row.get('ideas', 0),
            'percent': min(round(votes / item['max'] * 100), 100) if item['max'] else 0,
        })
    directions.sort(key=lambda d: -d['votes'])

    top = (Initiative.objects.filter(is_published=True)
           .annotate(comment_total=Count('comments'))
           .order_by('-vote_count', '-created_at')[:10])

    # Eng faol mualliflar — kim ko'p ovoz yig'gan
    authors = (Initiative.objects.filter(is_published=True)
               .values('author_name', 'author_id')
               .annotate(ideas=Count('id'), votes=Sum('vote_count'))
               .order_by('-votes')[:8])

    week_ago = timezone.now() - timezone.timedelta(days=7)

    return render(request, 'panel/voice_overview.html', {
        'directions': directions,
        'top': top,
        'authors': authors,
        'total_votes': sum(d['votes'] for d in directions),
        'total_ideas': sum(d['ideas'] for d in directions),
        'total_voters': InitiativeVote.objects.count(),
        'total_comments': InitiativeComment.objects.count(),
        'new_ideas_week': Initiative.objects.filter(created_at__gte=week_ago).count(),
        'new_votes_week': InitiativeVote.objects.filter(created_at__gte=week_ago).count(),
        'recent_comments': (InitiativeComment.objects
                            .select_related('initiative')
                            .order_by('-created_at')[:6]),
        'active': 'voice',
    })


@panel_required
def initiative_list(request):
    queryset = Initiative.objects.all()

    search = request.GET.get('q', '').strip()
    if search:
        queryset = queryset.filter(Q(title__icontains=search) |
                                   Q(description__icontains=search) |
                                   Q(author_name__icontains=search))

    direction = request.GET.get('yonalish')
    if direction:
        queryset = queryset.filter(direction=direction)

    status = request.GET.get('holat')
    if status in Status.values:
        queryset = queryset.filter(status=status)

    return render(request, 'panel/initiative_list.html', {
        'page_obj': _paginate(request, queryset),
        'search': search,
        'directions': DIRECTIONS,
        'active_direction': direction or '',
        'statuses': Status.choices,
        'active_status': status or '',
        'active': 'voice',
    })


@panel_required
def initiative_detail(request, pk):
    initiative = get_object_or_404(Initiative, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in Status.values:
            initiative.status = new_status
        initiative.admin_note = request.POST.get('admin_note', '')
        initiative.is_published = request.POST.get('is_published') == 'on'
        initiative.save(update_fields=['status', 'admin_note', 'is_published', 'updated_at'])

        if initiative.author_id:
            Notification.objects.create(
                user=initiative.author,
                title=f"Tashabbusingiz holati: {initiative.get_status_display()}",
                message=initiative.title,
                type='success' if new_status == Status.APPROVED else 'info',
                link=f"/tashabbuslar/ovoz/{initiative.direction}/",
            )
        messages.success(request, "Tashabbus yangilandi.")
        return redirect('panel:initiatives')

    rank = (Initiative.objects
            .filter(direction=initiative.direction, is_published=True,
                    vote_count__gt=initiative.vote_count)
            .count() + 1)

    return render(request, 'panel/initiative_detail.html', {
        'initiative': initiative,
        'statuses': Status.choices,
        'rank': rank,
        'voters': initiative.votes.select_related('user')[:20],
        'comments': initiative.comments.select_related('author')[:20],
        'vote_steps': [
            {'value': -10, 'label': "−10", 'css': 'panel-btn-outline'},
            {'value': -1, 'label': "−1", 'css': 'panel-btn-outline'},
            {'value': 1, 'label': "+1", 'css': 'panel-btn-success'},
            {'value': 10, 'label': "+10", 'css': 'panel-btn-success'},
            {'value': 50, 'label': "+50", 'css': 'panel-btn-success'},
        ],
        'active': 'voice',
    })


# ---------------------------------------------------------------- Chet eldagi tengdoshlar

@panel_required
def peer_list(request):
    queryset = Peer.objects.all()

    search = request.GET.get('q', '').strip()
    if search:
        queryset = queryset.filter(Q(full_name__icontains=search) |
                                   Q(institution__icontains=search) |
                                   Q(city__icontains=search))

    status = request.GET.get('holat')
    if status in Status.values:
        queryset = queryset.filter(status=status)

    return render(request, 'panel/peer_list.html', {
        'page_obj': _paginate(request, queryset),
        'search': search,
        'statuses': Status.choices,
        'active_status': status or '',
        'pending': Peer.objects.filter(status=Status.PENDING).count(),
        'approved': Peer.objects.filter(status=Status.APPROVED).count(),
        'countries': Peer.objects.filter(status=Status.APPROVED)
                                 .values('country').distinct().count(),
        'active': 'peers',
    })


@panel_required
@require_POST
def peer_status(request, pk):
    peer = get_object_or_404(Peer, pk=pk)
    new_status = request.POST.get('status')
    if new_status in Status.values:
        peer.status = new_status
        peer.save(update_fields=['status', 'updated_at'])

        if peer.user_id:
            Notification.objects.create(
                user=peer.user,
                title=f"«Chet eldagi tengdoshim» holati: {peer.get_status_display()}",
                message=peer.full_name,
                type='success' if new_status == Status.APPROVED else 'info',
                link='/chet-eldagi-tengdoshim/',
            )
        messages.success(request, "Holat yangilandi.")
    return redirect('panel:peers')


@panel_required
@require_POST
def initiative_votes(request, pk):
    """Tashabbus ovozini qo'lda sozlash (+/- yoki aniq son)."""
    initiative = get_object_or_404(Initiative, pk=pk)

    delta = request.POST.get('delta')
    exact = request.POST.get('exact')

    if delta:
        try:
            initiative.vote_count = max(initiative.vote_count + int(delta), 0)
        except ValueError:
            messages.error(request, "Noto'g'ri qiymat.")
            return redirect('panel:initiative_detail', pk=pk)
    elif exact not in (None, ''):
        try:
            initiative.vote_count = max(int(exact), 0)
        except ValueError:
            messages.error(request, "Noto'g'ri qiymat.")
            return redirect('panel:initiative_detail', pk=pk)
    else:
        return redirect('panel:initiative_detail', pk=pk)

    initiative.save(update_fields=['vote_count', 'updated_at'])
    messages.success(request, f"Ovoz soni {initiative.vote_count} ga o'rnatildi.")
    return redirect('panel:initiative_detail', pk=pk)
