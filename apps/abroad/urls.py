from django.urls import path

from . import views

app_name = 'abroad'

urlpatterns = [
    path('', views.peer_list, name='list'),
    path('qoshilish/', views.peer_join, name='join'),
    path('<int:pk>/', views.peer_detail, name='detail'),
]
