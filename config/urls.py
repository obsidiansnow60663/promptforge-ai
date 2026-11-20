from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from core import views

def redirect_home(request):
    return redirect('home')

urlpatterns = [
    path('', views.home, name='home'),
    path('health/', views.health, name='health'),
    path('accounts/login/', redirect_home, name='login'),
    path('accounts/signup/', redirect_home, name='signup'),
    path('accounts/logout/', redirect_home, name='logout'),
    path('run/', views.run, name='run'),
    path('history/', views.history, name='history'),
    path('compare/', views.compare, name='compare'),
    path('prompts/<int:pk>/', views.prompt_detail, name='prompt_detail'),
    path('prompts/<int:pk>/feedback/', views.feedback, name='feedback'),
    path('providers/', views.custom_providers, name='custom_providers'),
    path('providers/<int:pk>/delete/', views.delete_custom_provider, name='delete_custom_provider'),
    path('providers/test/', views.test_custom_provider, name='test_custom_provider'),
    path('admin/', admin.site.urls),
]
