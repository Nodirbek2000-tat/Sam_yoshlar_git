from django.urls import path

from . import import_views, views

app_name = 'panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Yangiliklar
    path('yangiliklar/', views.news_list, name='news'),
    path('yangiliklar/yangi/', views.news_form, name='news_create'),
    path('yangiliklar/<int:pk>/', views.news_form, name='news_edit'),
    path('yangiliklar/<int:pk>/ochirish/', views.news_delete, name='news_delete'),

    # Tadbirlar
    path('tadbirlar/', views.event_list, name='events'),
    path('tadbirlar/yangi/', views.event_form, name='event_create'),
    path('tadbirlar/<int:pk>/', views.event_form, name='event_edit'),
    path('tadbirlar/<int:pk>/ochirish/', views.event_delete, name='event_delete'),
    path('tadbirlar/<int:pk>/ishtirokchilar/', views.event_registrations,
         name='event_registrations'),
    path('yozilish/<int:pk>/qatnashdi/', views.toggle_attendance, name='toggle_attendance'),

    # E'lonlar
    path('elonlar/', views.announcement_list, name='announcements'),
    path('elonlar/yangi/', views.announcement_form, name='announcement_create'),
    path('elonlar/<int:pk>/', views.announcement_form, name='announcement_edit'),
    path('elonlar/<int:pk>/ochirish/', views.announcement_delete, name='announcement_delete'),

    # Foydalanuvchilar
    path('foydalanuvchilar/', views.user_list, name='users'),
    path('foydalanuvchilar/<int:pk>/', views.user_detail, name='user_detail'),
    path('foydalanuvchilar/<int:pk>/<str:action>/', views.user_toggle, name='user_toggle'),

    # Murojaat va takliflar
    path('murojaatlar/', views.appeal_list, name='appeals'),
    path('murojaatlar/<int:pk>/', views.appeal_detail, name='appeal_detail'),
    path('takliflar/', views.suggestion_list, name='suggestions'),
    path('takliflar/<int:pk>/holat/', views.suggestion_status, name='suggestion_status'),

    # StartUp va tashabbuslar
    path('startuplar/', views.startup_list, name='startups'),
    path('startuplar/<int:pk>/holat/', views.startup_status, name='startup_status'),
    path('muammolar/', views.problem_list, name='problems'),
    path('yechimlar/', views.solution_list, name='solutions'),
    path('yechimlar/<int:pk>/holat/', views.solution_status, name='solution_status'),

    # Yoshlar Ovozi
    path('yoshlar-ovozi/', views.voice_overview, name='voice'),
    path('tashabbuslar/', views.initiative_list, name='initiatives'),
    path('tashabbuslar/<int:pk>/', views.initiative_detail, name='initiative_detail'),
    path('tashabbuslar/<int:pk>/ovoz/', views.initiative_votes, name='initiative_votes'),

    # Chet eldagi tengdoshlar
    path('tengdoshlar/', views.peer_list, name='peers'),
    path('tengdoshlar/<int:pk>/holat/', views.peer_status, name='peer_status'),

    # JSON import / export
    path('import/', import_views.import_view, name='import'),
    path('import/eksport/', import_views.export_view, name='export'),

    # Sozlamalar
    path('sozlamalar/', views.settings_view, name='settings'),
    path('sozlamalar/rahbar/yangi/', views.leader_form, name='leader_create'),
    path('sozlamalar/rahbar/<int:pk>/', views.leader_form, name='leader_edit'),
    path('sozlamalar/rahbar/<int:pk>/ochirish/', views.leader_delete, name='leader_delete'),
    path('sozlamalar/vazifa/yangi/', views.task_form, name='task_create'),
    path('sozlamalar/vazifa/<int:pk>/', views.task_form, name='task_edit'),
    path('sozlamalar/vazifa/<int:pk>/ochirish/', views.task_delete, name='task_delete'),
]
