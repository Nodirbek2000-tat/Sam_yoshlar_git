from django.urls import path
from django.views.generic import RedirectView

from . import views, voice_views

app_name = 'initiatives'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),

    # Yoshlar tashabbuslari — reyting
    path('yoshlar/', voice_views.youth_view, name='youth'),
    path('yoshlar/<slug:direction_id>/', voice_views.youth_view, name='youth_direction'),

    # Bitta tashabbus
    path('tashabbus/<int:pk>/', voice_views.initiative_detail, name='initiative_detail'),
    path('tashabbus/<int:pk>/ovoz/', voice_views.vote_view, name='vote'),
    path('tashabbus/<int:pk>/ochirish/', voice_views.initiative_delete, name='initiative_delete'),

    # Tashabbus bildirish
    path('bildirish/', voice_views.initiative_create, name='initiative_create'),
    path('bildirish/<slug:direction_id>/', voice_views.initiative_create,
         name='initiative_create_direction'),

    # Eski havolalar
    path('ovoz/', RedirectView.as_view(pattern_name='initiatives:youth', permanent=False)),

    # Tashkilotlar anketasi (hozircha menyudan olib tashlangan, havola ishlaydi)
    path('tashkilotlar/', views.organization_form, name='organizations'),
    path('tashkilotlar/yuborildi/', views.organization_success, name='organization_success'),
    path('yechim/<int:problem_id>/', views.youth_view, name='youth_problem'),
    path('yechim/yuborildi/', views.solution_success, name='solution_success'),
]
