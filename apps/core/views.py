from django.views.generic import TemplateView

from .constants import Region
from .models import Leader, LeaderRole, Task


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cards'] = [
            {
                'title': "Tadbirkorlar",
                'icon': "💼",
                'description': "Yosh tadbirkorlar ro'yxati va ularning biznes loyihalari",
                'gradient': "linear-gradient(135deg, #1565C0 0%, #42A5F5 100%)",
                'shadow': "rgba(21, 101, 192, 0.35)",
                'url': 'cabinet:business',
            },
            {
                'title': "Startupperlar",
                'icon': "🚀",
                'description': "Innovatsion g'oyalar va startup loyihalar platformasi",
                'gradient': "linear-gradient(135deg, #7B1FA2 0%, #CE93D8 100%)",
                'shadow': "rgba(123, 31, 162, 0.35)",
                'url': 'startups:register',
            },
            {
                'title': "Tashabbuslar",
                'icon': "🌟",
                'description': "Tashkilotlar muammolari va yoshlar yechimlari platformasi",
                'gradient': "linear-gradient(135deg, #2E7D32 0%, #66BB6A 100%)",
                'shadow': "rgba(46, 125, 50, 0.35)",
                'url': 'initiatives:index',
            },
            {
                'title': "Ro'yxatdan o'tish",
                'icon': "📝",
                'description': "Platformaga qo'shiling va imkoniyatlardan foydalaning",
                'gradient': "linear-gradient(135deg, #E8A317 0%, #F5C842 100%)",
                'shadow': "rgba(232, 163, 23, 0.35)",
                'url': 'accounts:login',
            },
        ]
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
