from django import forms

from apps.core.constants import Region

from .models import (PROBLEM_QUESTIONS, Organization, OrganizationSphere, Problem, Solution)


class OrganizationForm(forms.ModelForm):
    """Anketaning 1-qadami — tashkilot ma'lumotlari."""

    class Meta:
        model = Organization
        fields = ['name', 'sphere', 'contact_person', 'phone', 'email', 'region', 'employees']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'startup-input',
                                           'placeholder': "Tashkilot nomini kiriting"}),
            'contact_person': forms.TextInput(attrs={'class': 'startup-input',
                                                     'placeholder': "Familiya Ism Sharif"}),
            'phone': forms.TextInput(attrs={'class': 'startup-input',
                                            'placeholder': '+998 90 123 45 67'}),
            'email': forms.EmailInput(attrs={'class': 'startup-input',
                                             'placeholder': 'email@example.com'}),
            'employees': forms.NumberInput(attrs={'class': 'startup-input', 'min': 1,
                                                  'placeholder': "Masalan: 45"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sphere'].widget = forms.Select(
            attrs={'class': 'startup-input'},
            choices=[('', "Tanlang")] + list(OrganizationSphere.choices),
        )
        self.fields['region'].widget = forms.Select(
            attrs={'class': 'startup-input'},
            choices=[('', "Tanlang")] + list(Region.choices),
        )
        for name in ('email', 'region', 'employees'):
            self.fields[name].required = False


class ProblemAnswersForm(forms.Form):
    """Anketaning 2-11 qadamlari — har bir kategoriya uchun bitta matn maydoni."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for item in PROBLEM_QUESTIONS:
            self.fields[f"problem_{item['category']}"] = forms.CharField(
                label=item['question'],
                required=item['category'] == 'main',
                widget=forms.Textarea(attrs={
                    'class': 'tashkilot-textarea',
                    'rows': 5,
                    'placeholder': "Javobingizni aniq faktlar bilan yozing...",
                }),
            )

    def clean(self):
        data = super().clean()
        answered = [v for k, v in data.items() if k.startswith('problem_') and v and v.strip()]
        if not answered:
            raise forms.ValidationError("Kamida bitta muammoni to'ldiring.")
        return data

    def create_problems(self, organization):
        """To'ldirilgan javoblarni Problem yozuvlariga aylantiradi."""
        created = []
        for item in PROBLEM_QUESTIONS:
            answer = (self.cleaned_data.get(f"problem_{item['category']}") or '').strip()
            if answer:
                created.append(Problem(organization=organization,
                                       category=item['category'],
                                       description=answer))
        return Problem.objects.bulk_create(created)


class SolutionForm(forms.ModelForm):
    """/tashabbuslar/yoshlar — yechim taklif qilish."""

    class Meta:
        model = Solution
        fields = ['author_name', 'author_phone', 'author_email', 'title', 'description',
                  'technologies', 'expected_result', 'attachment']
        widgets = {
            'author_name': forms.TextInput(attrs={'class': 'startup-input',
                                                  'placeholder': "Familiya Ism Sharif"}),
            'author_phone': forms.TextInput(attrs={'class': 'startup-input',
                                                   'placeholder': '+998 90 123 45 67'}),
            'author_email': forms.EmailInput(attrs={'class': 'startup-input',
                                                    'placeholder': 'email@example.com'}),
            'title': forms.TextInput(attrs={'class': 'startup-input',
                                            'placeholder': "Yechimingiz nomi"}),
            'description': forms.Textarea(attrs={'class': 'tashkilot-textarea', 'rows': 6,
                                                 'placeholder': "Yechimingiz qanday ishlaydi? "
                                                                "Bosqichma-bosqich tushuntiring."}),
            'technologies': forms.TextInput(attrs={'class': 'startup-input',
                                                   'placeholder': "Masalan: Python, Telegram bot, GPS"}),
            'expected_result': forms.Textarea(attrs={'class': 'tashkilot-textarea', 'rows': 4,
                                                     'placeholder': "Qanday natija kutilyapti?"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for name in ('author_phone', 'author_email', 'expected_result', 'attachment'):
            self.fields[name].required = False
        if user and user.is_authenticated and not self.is_bound:
            self.fields['author_name'].initial = user.full_name
            self.fields['author_phone'].initial = user.phone
            self.fields['author_email'].initial = user.email
