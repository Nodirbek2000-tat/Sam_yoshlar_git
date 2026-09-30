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
    # Tashkilot birinchi kirishda Telegram'ini maxsus havola orqali ulaydi
    path('api/telegram/tashkilot/', bot_api.bot_org_link, name='bot_org_link'),

    # Botning admin menyusi: statistika, majburiy kanallar, reklama
    path('api/telegram/admin/', bot_api.bot_admin_check, name='bot_admin_check'),
    path('api/telegram/statistika/', bot_api.bot_stats, name='bot_stats'),
    path('api/telegram/kanallar/', bot_api.bot_channels, name='bot_channels'),
    path('api/telegram/kanallar/<int:pk>/', bot_api.bot_channel_detail,
         name='bot_channel_detail'),
    path('api/telegram/obuna/', bot_api.bot_channel_joins, name='bot_channel_joins'),
    path('api/telegram/foydalanuvchilar/', bot_api.bot_users, name='bot_users'),
    path('api/telegram/postlar/', bot_api.bot_posts, name='bot_posts'),
    path('api/telegram/postlar/<int:pk>/natija/', bot_api.bot_post_result,
         name='bot_post_result'),
    path('api/telegram/reklama/', bot_api.bot_broadcast, name='bot_broadcast'),
    # Shaxsiy xabarlar (masalan, startapga investor qiziqdi) — bot egasiga yuboradi
    path('api/telegram/xabarlar/', bot_api.bot_messages, name='bot_messages'),
    path('api/telegram/xabarlar/natija/', bot_api.bot_messages_result,
         name='bot_messages_result'),
    # Server xatolari — bot adminlarga Telegram'da yuboradi
    path('api/telegram/xatolar/', bot_api.bot_errors, name='bot_errors'),
    path('api/telegram/reklama/<int:pk>/natija/', bot_api.bot_broadcast_result,
         name='bot_broadcast_result'),
]
