from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from .models import (Announcement, AnnouncementType, Event, EventRegistration, News,
                     NewsCategory)


class NewsListView(ListView):
    model = News
    template_name = 'content/news_list.html'
    context_object_name = 'news_list'
    paginate_by = 9

    def get_queryset(self):
        qs = News.objects.published().select_related('author')
        category = self.request.GET.get('kategoriya')
        if category in NewsCategory.values:
            qs = qs.filter(category=category)
        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(excerpt__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = NewsCategory.choices
        context['active_category'] = self.request.GET.get('kategoriya', '')
        context['search'] = self.request.GET.get('q', '')
        return context


class NewsDetailView(DetailView):
    model = News
    template_name = 'content/news_detail.html'
    context_object_name = 'news'

    def get_queryset(self):
        return News.objects.published().select_related('author')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        News.objects.filter(pk=obj.pk).update(views=F('views') + 1)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related'] = (News.objects.published()
                              .filter(category=self.object.category)
                              .exclude(pk=self.object.pk)[:3])
        return context


class EventListView(ListView):
    model = Event
    template_name = 'content/event_list.html'
    context_object_name = 'events'
    paginate_by = 9

    def get_queryset(self):
        qs = Event.objects.published()
        self.filter = self.request.GET.get('holat', 'all')
        now = timezone.now()
        if self.filter == 'kelasi':
            qs = qs.filter(starts_at__gte=now).order_by('starts_at')
        elif self.filter == 'otgan':
            qs = qs.filter(starts_at__lt=now).order_by('-starts_at')
        else:
            qs = qs.order_by('starts_at')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_filter'] = self.filter
        return context


class EventDetailView(DetailView):
    model = Event
    template_name = 'content/event_detail.html'
    context_object_name = 'event'

    def get_queryset(self):
        return Event.objects.published()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_registered'] = self.object.is_registered(self.request.user)
        return context


@login_required
@require_POST
def event_register(request, slug):
    """Tadbirga yozilish / bekor qilish."""
    event = get_object_or_404(Event.objects.published(), slug=slug)

    if event.is_past:
        messages.error(request, "Bu tadbir allaqachon o'tib ketgan.")
        return redirect(event.get_absolute_url())

    registration = EventRegistration.objects.filter(event=event, user=request.user).first()

    if registration and not registration.is_cancelled:
        registration.is_cancelled = True
        registration.save(update_fields=['is_cancelled', 'updated_at'])
        messages.info(request, "Tadbirdagi ishtirokingiz bekor qilindi.")
        return redirect(event.get_absolute_url())

    if event.is_full:
        messages.error(request, "Afsuski, joylar tugagan.")
        return redirect(event.get_absolute_url())

    if registration:
        registration.is_cancelled = False
        registration.save(update_fields=['is_cancelled', 'updated_at'])
    else:
        EventRegistration.objects.create(event=event, user=request.user)

    messages.success(request, f"«{event.title}» tadbiriga muvaffaqiyatli yozildingiz!")
    return redirect(event.get_absolute_url())


class AnnouncementListView(ListView):
    model = Announcement
    template_name = 'content/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 12

    def get_queryset(self):
        qs = Announcement.objects.filter(is_active=True)
        type_filter = self.request.GET.get('turi')
        if type_filter in AnnouncementType.values:
            qs = qs.filter(type=type_filter)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['types'] = AnnouncementType.choices
        context['active_type'] = self.request.GET.get('turi', '')
        return context


class AnnouncementDetailView(DetailView):
    model = Announcement
    template_name = 'content/announcement_detail.html'
    context_object_name = 'announcement'

    def get_queryset(self):
        return Announcement.objects.filter(is_active=True)
