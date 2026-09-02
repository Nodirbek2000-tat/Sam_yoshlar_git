from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('boshqaruv/', admin.site.urls),          # Django admin
    path('', include('apps.core.urls')),          # /, /about
    path('', include('apps.accounts.urls')),      # /login, /register, /logout
    path('', include('apps.content.urls')),       # /news, /events, /announcements
    path('startupperlar/', include('apps.startups.urls')),
    path('tashabbuslar/', include('apps.initiatives.urls')),
    path('chet-eldagi-tengdoshim/', include('apps.abroad.urls')),
    path('kabinet/', include('apps.cabinet.urls')),
    path('nazorat/', include('apps.panel.urls')),   # maxsus admin panel
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "sam-yosh tadbirkor.uz — boshqaruv"
admin.site.site_title = "sam-yosh tadbirkor"
admin.site.index_title = "Boshqaruv paneli"
