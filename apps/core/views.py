from django.db.models import Count, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from apps.abroad.models import Peer
from apps.content.models import Announcement, Event, News
from apps.initiatives.models import Initiative, Problem, Solution
from apps.startups.models import Startup

from .constants import Region
from .models import Leader, LeaderRole, Task


class HomeView(TemplateView):
    """Bosh sahifa — har bir bo'limdan tirik parcha ko'rsatadi."""

    template_name = 'core/home.html'

    # Bo'lim kartalari: ikonka sprite'dagi id, rang esa CSS o'zgaruvchisi
    SECTIONS = [
        {
            'title': "Tadbirkorlar",
            'icon': 'ic-briefcase',
            'tone': 'blue',
            'description': "Yosh tadbirkorlar ro'yxati va ularning biznes loyihalari",
            'url': 'cabinet:business',
        },
        {
            'title': "Startupperlar",
            'icon': 'ic-rocket',
            'tone': 'violet',
            'description': "Innovatsion g'oyalar va startap loyihalar platformasi",
            'url': 'startups:register',
        },
        {
            'title': "Tashabbuslar",
            'icon': 'ic-spark',
            'tone': 'green',
            'description': "Tashkilotlar muammolari va yoshlar yechimlari platformasi",
            'url': 'initiatives:index',
        },
        {
            'title': "Chet eldagi tengdoshim",
            'icon': 'ic-globe',
            'tone': 'teal',
            'description': "Chet elda o'qiyotgan va ishlayotgan tengdoshlar bilan aloqa",
            'url': 'abroad:list',
        },
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        context['sections'] = self.SECTIONS

        # --- Raqamlar ---
        context['stats'] = [
            {'value': Initiative.objects.filter(is_published=True).count(),
             'label': "Tashabbus", 'icon': 'ic-spark'},
            {'value': Initiative.objects.aggregate(total=Sum('vote_count'))['total'] or 0,
             'label': "Ovoz", 'icon': 'ic-vote'},
            {'value': Problem.objects.filter(is_published=True).count(),
             'label': "Tashkilot muammosi", 'icon': 'ic-clipboard'},
            {'value': Solution.objects.count(),
             'label': "Taklif etilgan yechim", 'icon': 'ic-bulb'},
        ]

        # --- Har bir bo'limdan parcha ---
        context['latest_news'] = News.objects.published()[:3]
        context['upcoming_events'] = (Event.objects.published()
                                      .filter(starts_at__gte=now)
                                      .order_by('starts_at')[:3])
        context['announcements'] = (Announcement.objects
                                    .filter(is_active=True)
                                    .order_by('-posted_at')[:4])
        context['top_initiatives'] = (Initiative.objects
                                      .filter(is_published=True)
                                      .annotate(comment_total=Count('comments'))
                                      .order_by('-vote_count')[:4])
        context['open_problems'] = (Problem.objects.filter(is_published=True)
                                    .select_related('organization')
                                    .annotate(solution_count=Count('solutions'))
                                    .order_by('-created_at')[:3])
        context['peers_count'] = Peer.objects.count()
        context['startups_count'] = Startup.objects.count()

        return context


class AboutView(TemplateView):
    template_name = 'core/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leaders = Leader.objects.filter(is_active=True)
        context['tasks'] = Task.objects.filter(is_active=True)
        context['heads'] = leaders.exclude(role=LeaderRole.MEMBER)
        context['members'] = leaders.filter(role=LeaderRole.MEMBER)
        context['regions'] = Region.choices
        return context
