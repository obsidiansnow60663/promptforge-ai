import logging
import time
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from .forms import CustomProviderForm, WorkForm
from .models import CustomProvider, Execution, Feedback, Prompt
from .services import PROVIDERS, Provider, ProviderError, execute, generate
logger = logging.getLogger(__name__)

@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})

def signup(request):
    return redirect('home')

def home(request):
    custom_providers_qs = CustomProvider.objects.filter(is_active=True)
    return render(request, 'core/home.html', {
        'form': WorkForm(),
        'prompts': Prompt.objects.all()[:8],
        'providers': PROVIDERS,
        'custom_providers': custom_providers_qs,
    })

@require_POST
def run(request):
    form = WorkForm(request.POST)
    mode = request.POST.get('mode')
    if not form.is_valid() or mode not in ('generate', 'generate_execute', 'execute'):
        return render(request, 'core/result.html', {'error': 'Periksa masukan, provider, dan model. Instruksi maksimal 20.000 karakter.'}, status=200)
    data = form.cleaned_data
    user = request.user if request.user.is_authenticated else None
    provider_name = data['provider']
    api_url = data.get('custom_api_url')
    api_key = data.get('custom_api_key')
    try:
        provider = Provider(provider_name, data['model'], api_url=api_url, api_key=api_key)
        saved_provider_name = provider.display_name if isinstance(getattr(provider, 'display_name', None), str) else provider_name
        prompt = None
        if mode != 'execute':
            analysis, optimized, review = generate(provider, data['text'], data['custom_instructions'])
            prompt = Prompt.objects.create(
                user=user, original=data['text'], optimized=optimized,
                analysis=analysis, review=review, provider=saved_provider_name, model=data['model']
            )
        else:
            optimized = data['text']
        execution = None
        if mode == 'generate_execute' and prompt.review.get('warning'):
            return render(request, 'core/result.html', {'prompt': prompt, 'error': 'Eksekusi dihentikan karena tinjauan menemukan masalah atau ambiguitas. Tinjau prompt terlebih dahulu.'})
        if mode != 'generate':
            execution = Execution.objects.create(
                user=user, prompt=prompt, input_text=optimized,
                provider=saved_provider_name, model=data['model'], status='running'
            )
            try:
                raw, final, review_out, usage, latency = execute(provider, optimized, data['adapt'])
                execution.raw_output, execution.final_output, execution.output_review, execution.usage, execution.latency_ms, execution.status = raw, final, review_out, usage, latency, 'completed'
            except ProviderError as exc:
                execution.status, execution.error = 'failed', str(exc)
            execution.save()
        return render(request, 'core/result.html', {'prompt': prompt, 'execution': execution})
    except ProviderError as exc:
        return render(request, 'core/result.html', {'error': str(exc)})

def history(request):
    return render(request, 'core/history.html', {'prompts': Prompt.objects.all()[:100], 'executions': Execution.objects.all()[:100]})

def prompt_detail(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    return render(request, 'core/detail.html', {'prompt': prompt, 'executions': prompt.executions.all()})

@require_POST
def feedback(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk)
    user = request.user if request.user.is_authenticated else None
    try: rating = int(request.POST.get('rating', '0'))
    except ValueError: rating = 0
    if 1 <= rating <= 5:
        Feedback.objects.create(user=user, prompt=prompt, rating=rating, comment=request.POST.get('comment', '')[:2000])
        messages.success(request, 'Terima kasih atas masukan Anda.')
    else: messages.error(request, 'Pilih nilai antara 1 dan 5.')
    return redirect('prompt_detail', pk=pk)

def compare(request):
    results = []
    custom_providers_qs = CustomProvider.objects.filter(is_active=True)
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        models = [(name, request.POST.get(name + '_model', '').strip()) for name in PROVIDERS]
        for cp in custom_providers_qs:
            val = request.POST.get(f'custom_{cp.id}_model', '').strip()
            if val:
                models.append((f'custom:{cp.id}', val))
        models = [(name, model) for name, model in models if model]
        if not text or len(text) > 20000 or len(models) < 2 or any(len(model) > 120 for _, model in models):
            return render(request, 'core/compare.html', {
                'error': 'Isi prompt hingga 20.000 karakter dan pilih sedikitnya dua model.',
                'text': text,
                'custom_providers': custom_providers_qs,
            })
        user = request.user if request.user.is_authenticated else None
        for name, model in models:
            provider = Provider(name, model)
            display = provider.display_name if isinstance(getattr(provider, 'display_name', None), str) else name
            item = Execution.objects.create(user=user, input_text=text, provider=display, model=model, status='running')
            try:
                raw, final, review, usage, latency = execute(provider, text, True)
                item.raw_output, item.final_output, item.output_review, item.usage, item.latency_ms, item.status = raw, final, review, usage, latency, 'completed'
            except ProviderError as exc:
                item.status, item.error = 'failed', str(exc)
            item.save()
            results.append(item)
    return render(request, 'core/compare.html', {'results': results, 'custom_providers': custom_providers_qs})

def custom_providers(request):
    providers_qs = CustomProvider.objects.all()
    form = CustomProviderForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cp = form.save()
        messages.success(request, f'Provider kustom "{cp.name}" berhasil disimpan.')
        return redirect('custom_providers')
    return render(request, 'core/providers.html', {'providers': providers_qs, 'form': form})

@require_POST
def delete_custom_provider(request, pk):
    cp = get_object_or_404(CustomProvider, pk=pk)
    name = cp.name
    cp.delete()
    messages.success(request, f'Provider "{name}" berhasil dihapus.')
    return redirect('custom_providers')

@require_POST
def test_custom_provider(request):
    pk = request.POST.get('provider_id')
    api_url = request.POST.get('api_url')
    api_key = request.POST.get('api_key', '')
    model = request.POST.get('model', '')
    name = request.POST.get('name', 'custom')

    try:
        if pk:
            cp = get_object_or_404(CustomProvider, pk=pk)
            provider = Provider(f'custom:{cp.id}', cp.default_model)
        else:
            if not api_url or not model:
                return JsonResponse({'success': False, 'error': 'URL Endpoint dan Model harus diisi.'})
            provider = Provider('custom', model, api_url=api_url, api_key=api_key, display_name=name)

        start = time.monotonic()
        res = provider.complete('You are a test assistant.', 'ping')
        latency = int((time.monotonic() - start) * 1000)
        return JsonResponse({
            'success': True,
            'latency_ms': latency,
            'message': f'Koneksi berhasil! Respons diterima dalam {latency} ms.',
            'response': res.text[:200]
        })
    except ProviderError as exc:
        return JsonResponse({'success': False, 'error': str(exc)})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': f'Koneksi gagal: {str(exc)}'})
