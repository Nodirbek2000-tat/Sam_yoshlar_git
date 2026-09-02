from django.urls import path

from . import views

app_name = 'startups'

urlpatterns = [
    path('', views.startup_register, name='register'),
    path('royxat/', views.StartupListView.as_view(), name='list'),
    path('yuborildi/', views.startup_success, name='success'),
]
