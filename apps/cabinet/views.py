from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.accounts.forms import ProfileForm
from apps.business.models import BusinessProfile, Document, GalleryImage, Product
from apps.content.models import EventRegistration
from apps.core.constants import Status
from apps.initiatives.directions import get_direction
from apps.initiatives.models import Initiative
from apps.startups.models import Startup

from .forms import (AppealForm, BusinessProfileForm, DocumentForm, GalleryImageForm,
                    ProductForm, SuggestionForm)
from .models import Appeal, Notification, Suggestion


@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'cabinet/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        business = BusinessProfile.objects.filter(user=user).first()

        context['business'] = business
        context['stats'] = [
            {'icon': '📨', 'label': "Murojaatlar", 'value': user.appeals.count(),
             'url': 'cabinet:appeals', 'tone': 'primary'},
            {'icon': '💡', 'label': "Takliflar", 'value': user.suggestions.count(),
             'url': 'cabinet:suggestions', 'tone': 'accent'},
            {'icon': '📅', 'label': "Tadbirlarim",
             'value': user.event_registrations.filter(is_cancelled=False).count(),
             'url': 'cabinet:events', 'tone': 'success'},
            {'icon': '📦', 'label': "Mahsulotlar",
             'value': business.products.count() if business else 0,
             'url': 'cabinet:products', 'tone': 'info'},
        ]
        context['recent_appeals'] = user.appeals.all()[:5]
        context['upcoming_events'] = (user.event_registrations
                                      .filter(is_cancelled=False,
                                              event__starts_at__gte=timezone.now())
                                      .select_related('event')
                                      .order_by('event__starts_at')[:3])
        context['startups'] = Startup.objects.filter(user=user)[:3]
        context['profile_completion'] = _profile_completion(user, business)
        return context


def _profile_completion(user, business):
    """Profil to'ldirilganlik foizi."""
    checks = [
        bool(user.full_name), bool(user.phone), bool(user.region),
        bool(user.district), bool(user.birth_date), bool(user.avatar), bool(user.bio),
        business is not None,
        bool(business and business.description),
        bool(business and business.logo),
    ]
    return round(sum(checks) / len(checks) * 100)


@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Profil ma'lumotlari saqlandi.")
        return redirect('cabinet:profile')
    return render(request, 'cabinet/profile.html', {'form': form})


@login_required
def business_view(request):
    business = BusinessProfile.objects.filter(user=request.user).first()
    form = BusinessProfileForm(request.POST or None, request.FILES or None, instance=business)
    if request.method == 'POST' and form.is_valid():
        profile = form.save(commit=False)
        profile.user = request.user
        profile.save()
        messages.success(request, "Biznes ma'lumotlari saqlandi.")
        return redirect('cabinet:business')
    return render(request, 'cabinet/business.html', {'form': form, 'business': business})


def _require_business(request):
    """Mahsulot/galereya/hujjat uchun avval biznes profil kerak."""
    business = BusinessProfile.objects.filter(user=request.user).first()
    if business is None:
        messages.warning(request, "Avval biznes profilingizni to'ldiring.")
    return business


@login_required
def products_view(request):
    business = _require_business(request)
    if business is None:
        return redirect('cabinet:business')

    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.business = business
        product.save()
        messages.success(request, "Mahsulot qo'shildi.")
        return redirect('cabinet:products')

    return render(request, 'cabinet/products.html', {
        'form': form,
        'products': business.products.all(),
    })


@login_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, business__user=request.user)
    product.delete()
    messages.info(request, "Mahsulot o'chirildi.")
    return redirect('cabinet:products')


@login_required
def gallery_view(request):
    business = _require_business(request)
    if business is None:
        return redirect('cabinet:business')

    form = GalleryImageForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        image = form.save(commit=False)
        image.business = business
        image.save()
        messages.success(request, "Rasm qo'shildi.")
        return redirect('cabinet:gallery')

    return render(request, 'cabinet/gallery.html', {
        'form': form,
        'images': business.gallery.all(),
    })


@login_required
@require_POST
def gallery_delete(request, pk):
    image = get_object_or_404(GalleryImage, pk=pk, business__user=request.user)
    image.delete()
    messages.info(request, "Rasm o'chirildi.")
    return redirect('cabinet:gallery')


@login_required
def documents_view(request):
    business = _require_business(request)
    if business is None:
        return redirect('cabinet:business')

    form = DocumentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        document = form.save(commit=False)
        document.business = business
        document.save()
        messages.success(request, "Hujjat yuklandi.")
        return redirect('cabinet:documents')

    return render(request, 'cabinet/documents.html', {
        'form': form,
        'documents': business.documents.all(),
    })


@login_required
@require_POST
def document_delete(request, pk):
    document = get_object_or_404(Document, pk=pk, business__user=request.user)
    document.delete()
    messages.info(request, "Hujjat o'chirildi.")
    return redirect('cabinet:documents')


@login_required
def appeals_view(request):
    form = AppealForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        appeal = form.save(commit=False)
        appeal.user = request.user
        appeal.save()
        messages.success(request, "Murojaatingiz yuborildi. Tez orada javob beramiz.")
        return redirect('cabinet:appeals')

    return render(request, 'cabinet/appeals.html', {
        'form': form,
        'appeals': request.user.appeals.all(),
    })


@login_required
def suggestions_view(request):
    form = SuggestionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        suggestion = form.save(commit=False)
        suggestion.user = request.user
        suggestion.save()
        messages.success(request, "Taklifingiz yuborildi. Rahmat!")
        return redirect('cabinet:suggestions')

    return render(request, 'cabinet/suggestions.html', {
        'form': form,
        'suggestions': request.user.suggestions.all(),
    })


@login_required
def my_events_view(request):
    registrations = (EventRegistration.objects
                     .filter(user=request.user)
                     .select_related('event')
                     .order_by('-event__starts_at'))
    now = timezone.now()
    return render(request, 'cabinet/events.html', {
        'upcoming': [r for r in registrations if r.event.starts_at >= now and not r.is_cancelled],
        'past': [r for r in registrations if r.event.starts_at < now],
        'cancelled': [r for r in registrations if r.is_cancelled and r.event.starts_at >= now],
    })


@login_required
def notifications_view(request):
    notifications = request.user.notifications.all()
    return render(request, 'cabinet/notifications.html', {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count(),
    })


@login_required
@require_POST
def notifications_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.info(request, "Barcha bildirishnomalar o'qilgan deb belgilandi.")
    return redirect('cabinet:notifications')


@login_required
def my_initiatives(request):
    """Kabinet — «Tashabbuslarim»: o'rin, ovoz va takliflar soni."""
    initiatives = (Initiative.objects
                   .filter(author=request.user)
                   .annotate(comment_total=Count('comments'))
                   .order_by('-vote_count', '-created_at'))

    for item in initiatives:
        item.direction_info = get_direction(item.direction)
        item.place = item.rank

    return render(request, 'cabinet/initiatives.html', {
        'initiatives': initiatives,
        'total_votes': sum(i.vote_count for i in initiatives),
        'total_comments': sum(i.comment_total for i in initiatives),
        'best_place': min((i.place for i in initiatives), default=None),
    })
