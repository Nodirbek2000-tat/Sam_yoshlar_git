from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import ListView

from apps.core.constants import Status

from .forms import StartupForm
from .models import Startup, StartupSphere


def startup_register(request):
    """/startupperlar — StartUp ro'yxatdan o'tkazish."""
    user = request.user if request.user.is_authenticated else None

    if request.method == 'POST':
        form = StartupForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            startup = form.save(commit=False)
            startup.user = user
            startup.save()
            messages.success(request, "StartUpingiz ro'yxatdan o'tkazildi!")
            return redirect('startups:success')
    else:
        form = StartupForm(user=user)

    context = {
        'form': form,
        'spheres': [
            {'value': value, 'label': label,
             'icon': _sphere_icon(value)}
            for value, label in StartupSphere.choices
        ],
    }
    return render(request, 'startups/register.html', context)


def _sphere_icon(value):
    from .models import STARTUP_SPHERE_ICONS
    return STARTUP_SPHERE_ICONS.get(value, 'ic-rocket')


def startup_success(request):
    return render(request, 'startups/success.html')


class StartupListView(ListView):
    """Tasdiqlangan startaplar ro'yxati."""

    model = Startup
    template_name = 'startups/list.html'
    context_object_name = 'startups'
    paginate_by = 12

    def get_queryset(self):
        qs = Startup.objects.filter(is_public=True, status=Status.APPROVED)
        sphere = self.request.GET.get('yonalish')
        if sphere in StartupSphere.values:
            qs = qs.filter(sphere=sphere)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['spheres'] = StartupSphere.choices
        context['active_sphere'] = self.request.GET.get('yonalish', '')
        return context
