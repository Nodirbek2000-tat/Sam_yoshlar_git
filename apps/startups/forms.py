from django import forms

from apps.core.constants import Region

from .models import Startup, StartupSphere, StartupStage


class StartupForm(forms.ModelForm):
    """/startupperlar — 2 qadamli ariza (bitta formada, JS bilan qadamlarga bo'linadi)."""

    class Meta:
        model = Startup
        fields = [
            'full_name', 'phone', 'email', 'birth_date', 'region', 'district',
            'name', 'sphere', 'stage', 'about', 'problem_solved', 'team_size',
            'needed_investment', 'pitch_file', 'website',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'startup-input',
                                                'placeholder': "Familiya Ism Sharif"}),
            'phone': forms.TextInput(attrs={'class': 'startup-input',
                                            'placeholder': '+998 90 123 45 67'}),
            'email': forms.EmailInput(attrs={'class': 'startup-input',
                                             'placeholder': 'email@example.com'}),
            'birth_date': forms.DateInput(attrs={'class': 'startup-input', 'type': 'date'}),
            'region': forms.Select(attrs={'class': 'startup-input'}),
            'district': forms.TextInput(attrs={'class': 'startup-input',
                                               'placeholder': "Tuman yoki shahar nomi"}),
            'name': forms.TextInput(attrs={'class': 'startup-input',
                                           'placeholder': "StartUp nomini kiriting"}),
            'stage': forms.Select(attrs={'class': 'startup-input'}),
            'about': forms.Textarea(attrs={'class': 'startup-textarea', 'rows': 5,
                                           'placeholder': "G'oyangiz nima haqida? Qanday ishlaydi?"}),
            'problem_solved': forms.Textarea(attrs={'class': 'startup-textarea', 'rows': 4,
                                                    'placeholder': "Qaysi muammoni hal qiladi?"}),
            'team_size': forms.NumberInput(attrs={'class': 'startup-input', 'min': 1}),
            'needed_investment': forms.NumberInput(attrs={'class': 'startup-input',
                                                          'placeholder': "Masalan: 50000000"}),
            'website': forms.URLInput(attrs={'class': 'startup-input',
                                             'placeholder': 'https://'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['region'].choices = [('', "Tanlang")] + list(Region.choices)
        self.fields['sphere'].widget = forms.RadioSelect(choices=StartupSphere.choices)
        self.fields['stage'].choices = StartupStage.choices
        self.fields['pitch_file'].widget.attrs.update({'accept': '.pdf,.ppt,.pptx,.doc,.docx'})

        for name in ('birth_date', 'district', 'problem_solved', 'needed_investment',
                     'pitch_file', 'website'):
            self.fields[name].required = False

        if user and user.is_authenticated and not self.is_bound:
            self.fields['full_name'].initial = user.full_name
            self.fields['phone'].initial = user.phone
            self.fields['email'].initial = user.email
            self.fields['region'].initial = user.region
            self.fields['district'].initial = user.district
            self.fields['birth_date'].initial = user.birth_date

    def clean_pitch_file(self):
        f = self.cleaned_data.get('pitch_file')
        if f and f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Fayl hajmi 10 MB dan oshmasligi kerak.")
        return f
