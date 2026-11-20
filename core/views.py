import logging
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from .forms import SignupForm, WorkForm
from .models import Execution, Feedback, Prompt
from .intelligence.pipeline import ClarificationRequired
from .services import PROVIDERS, Provider, ProviderError, execute, generate
logger = logging.getLogger(__name__)

@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})

def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(); login(request, user); return redirect('home')
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def home(request):
    return render(request, 'core/home.html', {'form': WorkForm(), 'prompts': Prompt.objects.filter(user=request.user)[:8], 'providers': PROVIDERS})

@login_required
@require_POST
def run(request):
    posted = request.POST
    if request.POST.get('mode') == 'clarify':
        pending = request.session.get('pending_prompt')
        if not pending:
            return render(request, 'core/result.html', {'error': 'Sesi klarifikasi berakhir. Silakan mulai kembali.'})
        posted = request.POST.copy()
        for key, value in pending.items(): posted[key] = value
        previous = pending.get('clarification', '')
        answer = request.POST.get('clarification', '').strip()
        posted['clarification'] = (previous + '\n' + answer).strip()
    form = WorkForm(posted)
    mode = posted.get('mode')
    if not form.is_valid() or mode not in ('generate', 'generate_execute', 'execute'):
        return render(request, 'core/result.html', {'error': 'Periksa masukan, provider, dan model. Instruksi maksimal 20.000 karakter.'}, status=200)
    data = form.cleaned_data
    try:
        provider = Provider(data['provider'], data['model'])
        if bool(data['reviewer_provider']) != bool(data['reviewer_model']):
            raise ProviderError('Isi provider dan model reviewer sekaligus.')
        reviewer = Provider(data['reviewer_provider'], data['reviewer_model']) if data['reviewer_provider'] else provider
        prompt = None
        if mode != 'execute':
            analysis, optimized, review = generate(provider, data['text'], data['custom_instructions'], reviewer, data['clarification'])
            request.session.pop('pending_prompt', None)
            prompt = Prompt.objects.create(user=request.user, original=data['text'], optimized=optimized, analysis=analysis, review=review, provider=data['provider'], model=data['model'])
        else:
            optimized = data['text']
        execution = None
        if mode == 'generate_execute' and prompt.review.get('warning'):
            return render(request, 'core/result.html', {'prompt': prompt, 'error': 'Eksekusi dihentikan karena tinjauan menemukan masalah atau ambiguitas. Tinjau prompt terlebih dahulu.'})
        if mode != 'generate':
            execution = Execution.objects.create(user=request.user, prompt=prompt, input_text=optimized, provider=data['provider'], model=data['model'], status='running')
            try:
                raw, final, review_out, usage, latency = execute(provider, optimized, data['adapt'], reviewer)
                execution.raw_output, execution.final_output, execution.output_review, execution.usage, execution.latency_ms, execution.status = raw, final, review_out, usage, latency, 'needs_review' if review_out.get('warning') else 'completed'
            except ProviderError as exc:
                execution.status, execution.error = 'failed', str(exc)
            execution.save()
        return render(request, 'core/result.html', {'prompt': prompt, 'execution': execution})
    except ClarificationRequired as exc:
        request.session['pending_prompt'] = {key: posted.get(key, '') for key in ('text', 'provider', 'model', 'custom_instructions', 'reviewer_provider', 'reviewer_model', 'adapt', 'mode', 'clarification')}
        return render(request, 'core/result.html', {'questions': exc.questions})
    except ProviderError as exc:
        return render(request, 'core/result.html', {'error': str(exc)})

@login_required
def history(request):
    return render(request, 'core/history.html', {'prompts': Prompt.objects.filter(user=request.user)[:100], 'executions': Execution.objects.filter(user=request.user)[:100]})

@login_required
def prompt_detail(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk, user=request.user)
    return render(request, 'core/detail.html', {'prompt': prompt, 'executions': prompt.executions.filter(user=request.user)})

@login_required
@require_POST
def feedback(request, pk):
    prompt = get_object_or_404(Prompt, pk=pk, user=request.user)
    try: rating = int(request.POST.get('rating', '0'))
    except ValueError: rating = 0
    if 1 <= rating <= 5:
        Feedback.objects.create(user=request.user, prompt=prompt, rating=rating, comment=request.POST.get('comment', '')[:2000]); messages.success(request, 'Terima kasih atas masukan Anda.')
    else: messages.error(request, 'Pilih nilai antara 1 dan 5.')
    return redirect('prompt_detail', pk=pk)

@login_required
def compare(request):
    results = []
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        models = [(name, request.POST.get(name + '_model', '').strip()) for name in PROVIDERS]
        models = [(name, model) for name, model in models if model]
        if not text or len(text) > 20000 or len(models) < 2 or any(len(model) > 120 for _, model in models):
            return render(request, 'core/compare.html', {'error': 'Isi prompt hingga 20.000 karakter dan pilih sedikitnya dua model.', 'text': text})
        for name, model in models:
            item = Execution.objects.create(user=request.user, input_text=text, provider=name, model=model, status='running')
            try:
                raw, final, review, usage, latency = execute(Provider(name, model), text, True)
                item.raw_output, item.final_output, item.output_review, item.usage, item.latency_ms, item.status = raw, final, review, usage, latency, 'needs_review' if review.get('warning') else 'completed'
            except ProviderError as exc:
                item.status, item.error = 'failed', str(exc)
            item.save()
            results.append(item)
    return render(request, 'core/compare.html', {'results': results})
