from django.urls import path

from . import views

app_name = 'content'

urlpatterns = [
    path('yangiliklar/', views.NewsListView.as_view(), name='news_list'),
    path('yangiliklar/<slug:slug>/', views.NewsDetailView.as_view(), name='news_detail'),
    path('tadbirlar/', views.EventListView.as_view(), name='event_list'),
    path('tadbirlar/<slug:slug>/', views.EventDetailView.as_view(), name='event_detail'),
    path('tadbirlar/<slug:slug>/yozilish/', views.event_register, name='event_register'),
    path('elonlar/', views.AnnouncementListView.as_view(), name='announcement_list'),
    path('elonlar/<slug:slug>/', views.AnnouncementDetailView.as_view(), name='announcement_detail'),
]
