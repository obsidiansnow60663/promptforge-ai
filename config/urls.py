from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from core import views
urlpatterns = [path('', views.home, name='home'), path('health/', views.health, name='health'), path('accounts/signup/', views.signup, name='signup'), path('accounts/login/', auth_views.LoginView.as_view(), name='login'), path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'), path('run/', views.run, name='run'), path('history/', views.history, name='history'), path('compare/', views.compare, name='compare'), path('prompts/<int:pk>/', views.prompt_detail, name='prompt_detail'), path('prompts/<int:pk>/feedback/', views.feedback, name='feedback'), path('admin/', admin.site.urls)]
