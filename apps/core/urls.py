from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('kengash-haqida/', views.AboutView.as_view(), name='about'),
]
