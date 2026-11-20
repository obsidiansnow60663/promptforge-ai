from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

@require_GET
def home(request):
    return render(request, 'core/home.html')

@require_GET
def health(request):
    # Liveness only: no database or external provider calls.
    return JsonResponse({'status': 'ok'})
