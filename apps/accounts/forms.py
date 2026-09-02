from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileForm(forms.ModelForm):
    """Kabinet — profilni to'ldirish.

    Ro'yxatdan o'tishda Telegram faqat ism va raqamni beradi;
    qolgan ma'lumotlarni foydalanuvchi shu yerda to'ldiradi.
    """

    class Meta:
        model = User
        fields = ['full_name', 'phone', 'email', 'region', 'district', 'birth_date',
                  'avatar', 'bio']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input',
                                             'placeholder': 'email@example.com'}),
            'region': forms.Select(attrs={'class': 'form-input form-select'}),
            'district': forms.TextInput(attrs={'class': 'form-input'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'avatar': forms.FileInput(attrs={'class': 'form-input'}),
            'bio': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = False
        self.fields['email'].label = "Email (ixtiyoriy)"

        # Telegram bergan xizmat pochtasini foydalanuvchiga ko'rsatmaymiz
        if self.instance and str(self.instance.email).endswith('@telegram.local'):
            self.initial['email'] = ''

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            # Bo'sh qoldirilsa, mavjud xizmat pochtasi saqlanib qoladi
            return self.instance.email
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Bu email boshqa hisobga biriktirilgan.")
        return email
