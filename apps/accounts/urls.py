from django.urls import path
from django.views.generic import RedirectView

from . import bot_api, telegram_views, views

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

    # Botning admin menyusi: statistika, majburiy kanallar, reklama
    path('api/telegram/admin/', bot_api.bot_admin_check, name='bot_admin_check'),
    path('api/telegram/statistika/', bot_api.bot_stats, name='bot_stats'),
    path('api/telegram/kanallar/', bot_api.bot_channels, name='bot_channels'),
    path('api/telegram/kanallar/<int:pk>/', bot_api.bot_channel_detail,
         name='bot_channel_detail'),
    path('api/telegram/obuna/', bot_api.bot_channel_joins, name='bot_channel_joins'),
    path('api/telegram/foydalanuvchilar/', bot_api.bot_users, name='bot_users'),
    path('api/telegram/reklama/', bot_api.bot_broadcast, name='bot_broadcast'),
    path('api/telegram/reklama/<int:pk>/natija/', bot_api.bot_broadcast_result,
         name='bot_broadcast_result'),
]
