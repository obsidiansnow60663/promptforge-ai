from django import forms
from .models import CustomProvider
from .services import PROVIDERS

class WorkForm(forms.Form):
    text = forms.CharField(max_length=20000, widget=forms.Textarea(attrs={'rows': 9, 'placeholder': 'Tuliskan instruksi, konteks, dan batasan Anda di sini…'}), label='Instruksi')
    provider = forms.CharField(max_length=64, initial='openai')
    model = forms.CharField(max_length=120, initial='gpt-4o-mini', help_text='Masukkan model yang tersedia pada akun provider Anda.')
    custom_api_url = forms.CharField(required=False, max_length=500, label='URL Endpoint Kustom')
    custom_api_key = forms.CharField(required=False, max_length=255, widget=forms.PasswordInput(render_value=True), label='API Key Kustom')
    custom_instructions = forms.CharField(required=False, max_length=3000, widget=forms.Textarea(attrs={'rows': 2}), label='Instruksi tambahan')
    reviewer_provider = forms.CharField(required=False, max_length=64)
    reviewer_model = forms.CharField(required=False, max_length=120)
    clarification = forms.CharField(required=False, max_length=5000)
    adapt = forms.BooleanField(required=False, initial=True, label='Adaptasi hasil ke Bahasa Indonesia')

class CustomProviderForm(forms.ModelForm):
    class Meta:
        model = CustomProvider
        fields = ('name', 'api_url', 'api_key', 'default_model')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Misal: Ollama Lokal, Groq, DeepSeek'}),
            'api_url': forms.TextInput(attrs={'placeholder': 'http://localhost:11434/v1 atau https://api.groq.com/openai/v1'}),
            'api_key': forms.PasswordInput(render_value=True, attrs={'placeholder': 'API Key (kosongkan jika provider lokal)'}),
            'default_model': forms.TextInput(attrs={'placeholder': 'llama3.2, deepseek-chat, gpt-4o, dll.'}),
        }
        labels = {
            'name': 'Nama Provider',
            'api_url': 'URL Endpoint / Base URL',
            'api_key': 'API Key (opsional)',
            'default_model': 'Model Default',
        }

    def clean_api_url(self):
        url = self.cleaned_data.get('api_url', '').strip()
        if not url:
            raise forms.ValidationError('URL Endpoint harus diisi.')
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        return url
