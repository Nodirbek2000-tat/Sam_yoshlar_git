"""API marshrutlari — `/api/v1/`."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from . import admin_views, auth_views, cabinet_views, views

app_name = 'api'

urlpatterns = [
    # --- Autentifikatsiya ---
    path('auth/info/', auth_views.auth_info, name='auth_info'),
    path('auth/telegram/', auth_views.telegram_login, name='telegram_login'),
    path('auth/login/', auth_views.password_login, name='password_login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/me/', auth_views.Me.as_view(), name='me'),

    # --- Shaxsiy kabinet (faqat o'z ma'lumoti) ---
    path('me/overview/', cabinet_views.CabinetOverview.as_view(), name='me_overview'),
    path('me/initiatives/', cabinet_views.MyInitiatives.as_view(), name='me_initiatives'),
    path('me/initiatives/<int:pk>/', cabinet_views.delete_initiative,
         name='me_initiative_delete'),
    path('me/events/', cabinet_views.MyEvents.as_view(), name='me_events'),
    path('me/comments/', cabinet_views.MyComments.as_view(), name='me_comments'),
    path('me/notifications/', cabinet_views.MyNotifications.as_view(), name='me_notifications'),
    path('me/appeals/', cabinet_views.MyAppeals.as_view(), name='me_appeals'),
    path('me/suggestions/', cabinet_views.MySuggestions.as_view(), name='me_suggestions'),
    path('me/problems/', views.MyProblems.as_view(), name='me_problems'),
    path('me/startup/', cabinet_views.MyStartup.as_view(), name='me_startup'),
    path('me/peer/', cabinet_views.MyPeer.as_view(), name='me_peer'),
    path('me/startups/', cabinet_views.MyStartups.as_view(), name='me_startups'),
    path('me/startups/<int:pk>/', cabinet_views.MyStartupDetail.as_view(),
         name='me_startup_detail'),
    path('me/business/', cabinet_views.MyBusiness.as_view(), name='me_business'),
    path('me/business/gallery/', cabinet_views.MyBusinessGallery.as_view(),
         name='me_business_gallery'),
    path('me/business/gallery/<int:pk>/', cabinet_views.delete_gallery_image,
         name='me_business_gallery_delete'),

    # --- Umumiy ---
    path('overview/', views.Overview.as_view(), name='overview'),
    path('reference/', views.ReferenceData.as_view(), name='reference'),

    # --- Yangiliklar ---
    path('news/', views.NewsList.as_view(), name='news_list'),
    path('news/<slug:slug>/', views.NewsDetail.as_view(), name='news_detail'),

    # --- Tadbirlar ---
    path('events/', views.EventList.as_view(), name='event_list'),
    path('events/<slug:slug>/', views.EventDetail.as_view(), name='event_detail'),
    path('events/<slug:slug>/register/', views.event_register, name='event_register'),

    # --- E'lonlar ---
    path('announcements/', views.AnnouncementList.as_view(), name='announcement_list'),
    path('announcements/<slug:slug>/', views.AnnouncementDetail.as_view(),
         name='announcement_detail'),

    # --- Tashabbuslar ---
    path('directions/', views.DirectionList.as_view(), name='directions'),
    path('initiatives/', views.InitiativeList.as_view(), name='initiative_list'),
    path('initiatives/<int:pk>/', views.InitiativeDetail.as_view(), name='initiative_detail'),
    path('initiatives/<int:pk>/vote/', views.initiative_vote, name='initiative_vote'),
    path('initiatives/<int:pk>/comments/', views.InitiativeComments.as_view(),
         name='initiative_comments'),

    # --- Tashkilot muammolari ---
    path('problems/', views.ProblemList.as_view(), name='problem_list'),
    path('problems/yozish/', views.ProblemCreate.as_view(), name='problem_create'),
    path('problems/<int:pk>/', views.ProblemDetail.as_view(), name='problem_detail'),
    path('problems/<int:pk>/solutions/', views.ProblemSolutions.as_view(),
         name='problem_solutions'),
    path('solutions/<int:pk>/like/', views.solution_like, name='solution_like'),

    # --- Chet eldagi tengdoshlar ---
    path('foydalanuvchilar/<int:pk>/', views.PublicProfile.as_view(), name='public_profile'),
    path('peers/', views.PeerList.as_view(), name='peer_list'),
    path('peers/<int:pk>/', views.PeerDetail.as_view(), name='peer_detail'),

    # --- Startaplar ---
    path('startups/', views.StartupList.as_view(), name='startup_list'),
    path('startups/<int:pk>/', views.StartupDetail.as_view(), name='startup_detail'),
    path('businesses/', views.BusinessList.as_view(), name='business_list'),
    path('businesses/<int:pk>/', views.BusinessDetail.as_view(), name='business_detail'),

    # --- Boshqaruv paneli (faqat adminlar; ruxsat yo'q bo'lsa 404) ---
    path('panel/overview/', admin_views.PanelOverview.as_view(), name='panel_overview'),
    path('panel/users/', admin_views.PanelUsers.as_view(), name='panel_users'),
    path('panel/users/<int:pk>/', admin_views.PanelUserDetail.as_view(),
         name='panel_user_detail'),
    path('panel/users/<int:pk>/profil/', admin_views.moderate_profile,
         name='panel_moderate_profile'),
    path('panel/users/<int:pk>/admin/', admin_views.toggle_admin, name='panel_toggle_admin'),
    path('panel/initiatives/<int:pk>/votes/', admin_views.adjust_votes, name='panel_votes'),
    path('panel/organizations/', admin_views.PanelOrganizations.as_view(),
         name='panel_organizations'),
    path('panel/organizations/<int:pk>/parol/', admin_views.reset_organization_password,
         name='panel_org_password'),
    path('panel/news/', admin_views.PanelNews.as_view(), name='panel_news'),
    path('panel/news/<int:pk>/tahrir/', admin_views.PanelNewsDetail.as_view(),
         name='panel_news_detail'),
    path('panel/import/initiatives/', admin_views.PanelImport.as_view(),
         name='panel_import'),
    path('panel/import/announcements/', admin_views.PanelImportAnnouncements.as_view(),
         name='panel_import_announcements'),
    path('panel/import/organizations/', admin_views.PanelImportOrganizations.as_view(),
         name='panel_import_organizations'),
    path('panel/events/', admin_views.PanelEvents.as_view(), name='panel_events'),
    path('panel/events/<int:pk>/tahrir/', admin_views.PanelEventDetail.as_view(),
         name='panel_event_detail'),
    path('panel/announcements/', admin_views.PanelAnnouncements.as_view(),
         name='panel_announcements'),
    path('panel/announcements/<int:pk>/tahrir/',
         admin_views.PanelAnnouncementDetail.as_view(), name='panel_announcement_detail'),
    path('panel/<slug:resource>/<int:pk>/holat/', admin_views.panel_moderate,
         name='panel_moderate'),
    path('panel/<slug:resource>/hammasi/', admin_views.panel_delete_all,
         name='panel_delete_all'),
    path('panel/<slug:resource>/', admin_views.PanelList.as_view(), name='panel_list'),
    path('panel/<slug:resource>/<int:pk>/', admin_views.panel_delete, name='panel_delete'),
]
