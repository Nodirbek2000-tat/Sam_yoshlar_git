from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.constants import Region, Status

from .countries import COUNTRIES
from .models import Peer, PeerPurpose


class PeerForm(forms.ModelForm):
    """«Men ham chet eldaman» — ro'yxatdan o'tish formasi."""

    class Meta:
        model = Peer
        fields = ['full_name', 'photo', 'country', 'city', 'home_region', 'purpose',
                  'institution', 'field', 'since_year', 'about', 'can_help',
                  'telegram', 'instagram', 'email', 'phone']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input',
                                                'placeholder': "Familiya Ism"}),
            'photo': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'city': forms.TextInput(attrs={'class': 'form-input', 'placeholder': "Masalan: Berlin"}),
            'institution': forms.TextInput(attrs={'class': 'form-input',
                                                  'placeholder': "Universitet yoki kompaniya nomi"}),
            'field': forms.TextInput(attrs={'class': 'form-input',
                                            'placeholder': "Masalan: Kompyuter injiniringi"}),
            'since_year': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': "2023",
                                                   'min': 1990, 'max': 2100}),
            'about': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 5,
                                           'placeholder': "O'zingiz haqingizda qisqacha: qanday "
                                                          "yo'l bilan bordingiz, nima bilan "
                                                          "shug'ullanasiz?"}),
            'can_help': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 4,
                                              'placeholder': "Yurtdagi tengdoshlaringizga nimada "
                                                             "yordam bera olasiz? Masalan: hujjat "
                                                             "topshirish, grant, til imtihoni..."}),
            'telegram': forms.TextInput(attrs={'class': 'form-input', 'placeholder': "@username"}),
            'instagram': forms.TextInput(attrs={'class': 'form-input', 'placeholder': "@username"}),
            'email': forms.EmailInput(attrs={'class': 'form-input',
                                             'placeholder': "email@example.com"}),
            'phone': forms.TextInput(attrs={'class': 'form-input',
                                            'placeholder': "+998 90 123 45 67"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['country'].widget = forms.Select(attrs={'class': 'form-input form-select'})
        self.fields['home_region'].widget = forms.Select(
            attrs={'class': 'form-input form-select'},
            choices=[('', "Tanlang")] + list(Region.choices),
        )
        self.fields['purpose'].widget = forms.RadioSelect(choices=PeerPurpose.choices)

        for name in ('photo', 'city', 'home_region', 'institution', 'field', 'since_year',
                     'can_help', 'telegram', 'instagram', 'email', 'phone'):
            self.fields[name].required = False

        if user is not None and user.is_authenticated and not self.is_bound:
            self.fields['full_name'].initial = user.full_name
            self.fields['email'].initial = user.email
            self.fields['home_region'].initial = user.region

    def clean(self):
        data = super().clean()
        contacts = [data.get('telegram'), data.get('instagram'), data.get('email'),
                    data.get('phone')]
        if not any(c for c in contacts if c):
            raise forms.ValidationError(
                "Kamida bitta aloqa usulini qoldiring — Telegram, Instagram, email yoki telefon."
            )
        return data


def peer_list(request):
    """/chet-eldagi-tengdoshim/ — tasdiqlangan tengdoshlar ro'yxati."""
    queryset = Peer.objects.filter(is_published=True, status=Status.APPROVED)

    search = request.GET.get('q', '').strip()
    if search:
        queryset = queryset.filter(
            Q(full_name__icontains=search) | Q(institution__icontains=search)
            | Q(field__icontains=search) | Q(city__icontains=search)
        )

    country = request.GET.get('davlat')
    if country:
        queryset = queryset.filter(country=country)

    purpose = request.GET.get('maqsad')
    if purpose in PeerPurpose.values:
        queryset = queryset.filter(purpose=purpose)

    # Faqat odam bor davlatlar ko'rsatiladi
    counts = dict(Peer.objects.filter(is_published=True, status=Status.APPROVED)
                  .values_list('country')
                  .annotate(total=Count('id')))
    countries = [
        {'code': code, 'name': name, 'short': short, 'color': color,
         'count': counts.get(code, 0)}
        for code, name, short, color in COUNTRIES if counts.get(code)
    ]
    countries.sort(key=lambda c: -c['count'])

    return render(request, 'abroad/list.html', {
        'page_obj': Paginator(queryset, 12).get_page(request.GET.get('page')),
        'countries': countries,
        'purposes': PeerPurpose.choices,
        'search': search,
        'active_country': country or '',
        'active_purpose': purpose or '',
        'total': queryset.count(),
        'country_total': len(countries),
    })


def peer_detail(request, pk):
    peer = get_object_or_404(Peer, pk=pk, is_published=True, status=Status.APPROVED)
    return render(request, 'abroad/detail.html', {
        'peer': peer,
        'others': (Peer.objects
                   .filter(country=peer.country, is_published=True, status=Status.APPROVED)
                   .exclude(pk=peer.pk)[:4]),
    })


def peer_join(request):
    """«Men ham chet eldaman» — anketa. Admin tasdiqlagach ro'yxatda ko'rinadi."""
    user = request.user if request.user.is_authenticated else None
    form = PeerForm(request.POST or None, request.FILES or None, user=user)

    if request.method == 'POST' and form.is_valid():
        peer = form.save(commit=False)
        peer.user = user
        peer.save()
        messages.success(
            request,
            "Ma'lumotlaringiz qabul qilindi! Admin tasdiqlagach ro'yxatda paydo bo'lasiz.",
        )
        return redirect('abroad:list')

    return render(request, 'abroad/join.html', {'form': form})
