from django.urls import path
from django.views.generic import RedirectView

from . import telegram_views, views

app_name = 'accounts'

urlpatterns = [
    # Kirish va ro'yxatdan o'tish — faqat Telegram orqali
    path('kirish/', telegram_views.telegram_login, name='login'),
    path('telegram/', RedirectView.as_view(pattern_name='accounts:login', permanent=False),
         name='telegram_login'),
    path("royxatdan-otish/",
         RedirectView.as_view(pattern_name='accounts:login', permanent=False),
         name='register'),

    path('chiqish/', views.logout_view, name='logout'),

    # Bot chaqiradigan API
    path('api/telegram/kod/', telegram_views.telegram_issue_code, name='telegram_issue_code'),
]
