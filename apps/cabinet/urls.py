from django.urls import path

from . import views

app_name = 'cabinet'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('profil/', views.profile_view, name='profile'),
    path('biznes/', views.business_view, name='business'),
    path('mahsulotlar/', views.products_view, name='products'),
    path('mahsulotlar/<int:pk>/ochirish/', views.product_delete, name='product_delete'),
    path('galereya/', views.gallery_view, name='gallery'),
    path('galereya/<int:pk>/ochirish/', views.gallery_delete, name='gallery_delete'),
    path('hujjatlar/', views.documents_view, name='documents'),
    path('hujjatlar/<int:pk>/ochirish/', views.document_delete, name='document_delete'),
    path('murojaatlar/', views.appeals_view, name='appeals'),
    path('takliflar/', views.suggestions_view, name='suggestions'),
    path('tashabbuslarim/', views.my_initiatives, name='initiatives'),
    path('tadbirlarim/', views.my_events_view, name='events'),
    path('bildirishnomalar/', views.notifications_view, name='notifications'),
    path('bildirishnomalar/oqildi/', views.notifications_read_all, name='notifications_read_all'),
]
