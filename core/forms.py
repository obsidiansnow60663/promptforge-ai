from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .services import PROVIDERS

class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username',)

class WorkForm(forms.Form):
    text = forms.CharField(max_length=20000, widget=forms.Textarea(attrs={'rows': 9, 'placeholder': 'Tuliskan instruksi, konteks, dan batasan Anda di sini…'}), label='Instruksi')
    provider = forms.ChoiceField(choices=[(k, k.title()) for k in PROVIDERS])
    model = forms.CharField(max_length=120, initial='gpt-4o-mini', help_text='Masukkan model yang tersedia pada akun provider Anda.')
    custom_instructions = forms.CharField(required=False, max_length=3000, widget=forms.Textarea(attrs={'rows': 2}), label='Instruksi tambahan')
    adapt = forms.BooleanField(required=False, initial=True, label='Adaptasi hasil ke Bahasa Indonesia')
