from django import forms

from apps.business.models import BusinessProfile, Document, GalleryImage, Product

from .models import Appeal, Suggestion


class BusinessProfileForm(forms.ModelForm):
    class Meta:
        model = BusinessProfile
        fields = ['name', 'sphere', 'stir', 'founded_year', 'employees', 'region', 'district',
                  'address', 'description', 'logo', 'website', 'phone', 'email', 'telegram',
                  'instagram', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'sphere': forms.Select(attrs={'class': 'form-input form-select'}),
            'stir': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '123456789'}),
            'founded_year': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '2020'}),
            'employees': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'region': forms.Select(attrs={'class': 'form-input form-select'}),
            'district': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 5}),
            'logo': forms.FileInput(attrs={'class': 'form-input'}),
            'website': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'telegram': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '@username'}),
            'instagram': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '@username'}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'unit', 'image', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '150000'}),
            'unit': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'dona'}),
            'image': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        }


class GalleryImageForm(forms.ModelForm):
    class Meta:
        model = GalleryImage
        fields = ['image', 'caption']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'caption': forms.TextInput(attrs={'class': 'form-input', 'placeholder': "Rasm izohi"}),
        }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'type', 'file', 'note']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'type': forms.Select(attrs={'class': 'form-input form-select'}),
            'file': forms.FileInput(attrs={'class': 'form-input'}),
            'note': forms.TextInput(attrs={'class': 'form-input'}),
        }


class AppealForm(forms.ModelForm):
    class Meta:
        model = Appeal
        fields = ['subject', 'category', 'message', 'attachment']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-input',
                                              'placeholder': "Murojaat mavzusi"}),
            'category': forms.Select(attrs={'class': 'form-input form-select'}),
            'message': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 6,
                                             'placeholder': "Murojaatingizni batafsil yozing..."}),
            'attachment': forms.FileInput(attrs={'class': 'form-input'}),
        }


class SuggestionForm(forms.ModelForm):
    class Meta:
        model = Suggestion
        fields = ['title', 'description', 'expected_benefit']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input',
                                            'placeholder': "Taklifingiz nomi"}),
            'description': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 5,
                                                 'placeholder': "Taklifingizni tushuntiring..."}),
            'expected_benefit': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3,
                                                      'placeholder': "Qanday foyda keltiradi?"}),
        }
