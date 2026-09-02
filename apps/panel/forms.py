from django import forms
from django.contrib.auth import get_user_model

from apps.content.models import Announcement, Event, News
from apps.core.models import Leader, SiteSetting, Task

User = get_user_model()

INPUT = {'class': 'panel-input'}
TEXTAREA = {'class': 'panel-input panel-textarea', 'rows': 6}
SELECT = {'class': 'panel-input panel-select'}
FILE = {'class': 'panel-file'}


class NewsForm(forms.ModelForm):
    class Meta:
        model = News
        fields = ['title', 'category', 'excerpt', 'body', 'image', 'author_name',
                  'published_at', 'is_published', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={**INPUT, 'placeholder': "Yangilik sarlavhasi"}),
            'category': forms.Select(attrs=SELECT),
            'excerpt': forms.Textarea(attrs={**TEXTAREA, 'rows': 3,
                                             'placeholder': "Kartada ko'rinadigan qisqa matn"}),
            'body': forms.Textarea(attrs={**TEXTAREA, 'rows': 12,
                                          'placeholder': "Yangilikning to'liq matni"}),
            'image': forms.FileInput(attrs={**FILE, 'accept': 'image/*'}),
            'author_name': forms.TextInput(attrs={**INPUT, 'placeholder': "Muallif ismi"}),
            'published_at': forms.DateTimeInput(attrs={**INPUT, 'type': 'datetime-local'},
                                                format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['published_at'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'starts_at', 'ends_at', 'location', 'region',
                  'capacity', 'image', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={**INPUT, 'placeholder': "Tadbir nomi"}),
            'description': forms.Textarea(attrs={**TEXTAREA,
                                                 'placeholder': "Tadbir haqida batafsil"}),
            'starts_at': forms.DateTimeInput(attrs={**INPUT, 'type': 'datetime-local'},
                                             format='%Y-%m-%dT%H:%M'),
            'ends_at': forms.DateTimeInput(attrs={**INPUT, 'type': 'datetime-local'},
                                           format='%Y-%m-%dT%H:%M'),
            'location': forms.TextInput(attrs={**INPUT, 'placeholder': "Toshkent, IT Park"}),
            'region': forms.Select(attrs=SELECT),
            'capacity': forms.NumberInput(attrs={**INPUT, 'min': 1}),
            'image': forms.FileInput(attrs={**FILE, 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('starts_at', 'ends_at'):
            self.fields[name].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']
        self.fields['ends_at'].required = False

    def clean(self):
        data = super().clean()
        starts_at, ends_at = data.get('starts_at'), data.get('ends_at')
        if starts_at and ends_at and ends_at < starts_at:
            self.add_error('ends_at', "Tugash vaqti boshlanish vaqtidan oldin bo'lolmaydi.")
        return data


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'type', 'body', 'file', 'posted_at', 'deadline', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={**INPUT, 'placeholder': "E'lon sarlavhasi"}),
            'type': forms.Select(attrs=SELECT),
            'body': forms.Textarea(attrs={**TEXTAREA, 'placeholder': "E'lon matni, shartlari"}),
            'file': forms.FileInput(attrs=FILE),
            'posted_at': forms.DateInput(attrs={**INPUT, 'type': 'date'}, format='%Y-%m-%d'),
            'deadline': forms.DateInput(attrs={**INPUT, 'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['posted_at'].input_formats = ['%Y-%m-%d']
        self.fields['deadline'].input_formats = ['%Y-%m-%d']
        self.fields['deadline'].required = False

    def clean(self):
        data = super().clean()
        posted_at, deadline = data.get('posted_at'), data.get('deadline')
        if posted_at and deadline and deadline < posted_at:
            self.add_error('deadline', "Muddat joylangan sanadan oldin bo'lolmaydi.")
        return data


class UserForm(forms.ModelForm):
    """Adminlar foydalanuvchi ma'lumotlarini tahrirlaydi (parolga tegilmaydi)."""

    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone', 'role', 'region', 'district',
                  'is_active', 'is_verified', 'is_staff']
        widgets = {
            'full_name': forms.TextInput(attrs=INPUT),
            'email': forms.EmailInput(attrs=INPUT),
            'phone': forms.TextInput(attrs=INPUT),
            'role': forms.Select(attrs=SELECT),
            'region': forms.Select(attrs=SELECT),
            'district': forms.TextInput(attrs=INPUT),
        }


class AppealResponseForm(forms.Form):
    status = forms.ChoiceField(label="Holat", widget=forms.Select(attrs=SELECT))
    response = forms.CharField(
        label="Javob", required=False,
        widget=forms.Textarea(attrs={**TEXTAREA, 'rows': 5,
                                     'placeholder': "Foydalanuvchiga javobingiz..."}),
    )

    def __init__(self, *args, **kwargs):
        from apps.core.constants import Status
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = Status.choices


class SiteSettingForm(forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = ['site_name', 'tagline', 'mission', 'vision', 'charter_file',
                  'address', 'phone', 'email', 'work_hours',
                  'telegram_url', 'instagram_url', 'facebook_url', 'youtube_url']
        widgets = {
            'site_name': forms.TextInput(attrs=INPUT),
            'tagline': forms.Textarea(attrs={**TEXTAREA, 'rows': 3}),
            'mission': forms.Textarea(attrs={**TEXTAREA, 'rows': 3}),
            'vision': forms.Textarea(attrs={**TEXTAREA, 'rows': 3}),
            'charter_file': forms.FileInput(attrs=FILE),
            'address': forms.TextInput(attrs=INPUT),
            'phone': forms.TextInput(attrs=INPUT),
            'email': forms.EmailInput(attrs=INPUT),
            'work_hours': forms.TextInput(attrs=INPUT),
            'telegram_url': forms.URLInput(attrs=INPUT),
            'instagram_url': forms.URLInput(attrs=INPUT),
            'facebook_url': forms.URLInput(attrs=INPUT),
            'youtube_url': forms.URLInput(attrs=INPUT),
        }


class LeaderForm(forms.ModelForm):
    class Meta:
        model = Leader
        fields = ['full_name', 'position', 'role', 'bio', 'photo', 'region', 'order', 'is_active']
        widgets = {
            'full_name': forms.TextInput(attrs=INPUT),
            'position': forms.TextInput(attrs=INPUT),
            'role': forms.Select(attrs=SELECT),
            'bio': forms.Textarea(attrs={**TEXTAREA, 'rows': 4}),
            'photo': forms.FileInput(attrs={**FILE, 'accept': 'image/*'}),
            'region': forms.Select(attrs=SELECT),
            'order': forms.NumberInput(attrs=INPUT),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['text', 'order', 'is_active']
        widgets = {
            'text': forms.TextInput(attrs=INPUT),
            'order': forms.NumberInput(attrs=INPUT),
        }
