"""Boshqaruv paneli uchun API (`/api/v1/panel/`).

Faqat tasdiqlangan adminlar kira oladi. Ruxsati yo'q bo'lsa **404** qaytadi —
403 emas: shunda panel borligi ham oshkor bo'lmaydi.
"""
import json
import secrets
from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Greatest
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abroad.models import Peer
from apps.business.models import BusinessProfile
from apps.cabinet.models import Appeal, Notification, Suggestion
from apps.content.models import Announcement, Event, News
from apps.core.constants import Region, Status
from apps.initiatives.directions import DIRECTIONS
from apps.initiatives.models import (Initiative, InitiativeComment, Organization,
                                     OrganizationSphere, Problem, ProblemCategory,
                                     Solution)
from apps.panel.mixins import is_panel_admin
from apps.startups.models import Startup

from . import serializers as s
from .onboarding import onboarding_step

User = get_user_model()


class IsPanelAdmin(BasePermission):
    """Ruxsat yo'q bo'lsa 404 — panel mavjudligi ham bilinmasin."""

    def has_permission(self, request, view):
        if not is_panel_admin(request.user):
            raise Http404
        return True


class PanelOverview(APIView):
    permission_classes = [IsPanelAdmin]

    def get(self, request):
        now = timezone.now()

        return Response({
            'stats': [
                {'key': 'users', 'label': "Foydalanuvchilar", 'icon': 'users',
                 'value': User.objects.count()},
                {'key': 'initiatives', 'label': "Tashabbuslar", 'icon': 'spark',
                 'value': Initiative.objects.count()},
                {'key': 'votes', 'label': "Berilgan ovozlar", 'icon': 'vote',
                 'value': Initiative.objects.aggregate(t=Sum('vote_count'))['t'] or 0},
                {'key': 'news', 'label': "Yangiliklar", 'icon': 'news',
                 'value': News.objects.count()},
                {'key': 'events', 'label': "Tadbirlar", 'icon': 'calendar',
                 'value': Event.objects.count()},
                {'key': 'announcements', 'label': "E'lonlar", 'icon': 'megaphone',
                 'value': Announcement.objects.count()},
                {'key': 'problems', 'label': "Tashkilot muammolari", 'icon': 'clipboard',
                 'value': Problem.objects.count()},
                {'key': 'peers', 'label': "Chet eldagi tengdoshlar", 'icon': 'globe',
                 'value': Peer.objects.count()},
            ],
            # E'tibor talab qiladigan narsalar — panelning asosiy ishi shu
            'pending': [
                {'key': 'appeals', 'label': "Javob kutayotgan murojaatlar",
                 'icon': 'mail', 'href': '/nazorat/murojaatlar',
                 'value': Appeal.objects.filter(status=Status.PENDING).count()},
                {'key': 'suggestions', 'label': "Ko'rilmagan takliflar",
                 'icon': 'bulb', 'href': '/nazorat/takliflar',
                 'value': Suggestion.objects.filter(status=Status.PENDING).count()},
                {'key': 'startups', 'label': "Tasdiq kutayotgan startaplar",
                 'icon': 'rocket', 'href': '/nazorat/startaplar',
                 'value': Startup.objects.filter(status=Status.PENDING).count()},
                {'key': 'solutions', 'label': "Yangi yechimlar",
                 'icon': 'check', 'href': '/nazorat/yechimlar',
                 'value': Solution.objects.filter(status=Status.PENDING).count()},
                {'key': 'peers', 'label': "Tasdiq kutayotgan tengdoshlar",
                 'icon': 'globe', 'href': '/nazorat/tengdoshlar',
                 'value': Peer.objects.filter(status=Status.PENDING).count()},
            ],
            'recent_users': [
                {'id': user.pk, 'full_name': user.full_name, 'email': user.email,
                 'role': user.role, 'role_display': user.get_role_display(),
                 'initials': user.initials, 'is_verified': user.is_verified,
                 'created_at': user.date_joined}
                for user in User.objects.order_by('-date_joined')[:6]
            ],
            'top_initiatives': s.InitiativeListSerializer(
                Initiative.objects.annotate(comment_total=Count('comments', distinct=True))
                .order_by('-vote_count')[:5],
                many=True, context={'request': request}).data,
            'upcoming_events': s.EventListSerializer(
                Event.objects.filter(starts_at__gte=now).order_by('starts_at')[:4],
                many=True, context={'request': request}).data,
        })


class PanelUsers(APIView):
    permission_classes = [IsPanelAdmin]

    def get(self, request):
        queryset = User.objects.order_by('-date_joined')

        search = request.query_params.get('q')
        if search:
            queryset = queryset.filter(full_name__icontains=search)

        role = request.query_params.get('rol')
        if role:
            queryset = queryset.filter(role=role)

        # Tadbirkor/startupper anketasi kengash tekshiruvini kutayotganlar
        if request.query_params.get('tekshiruv'):
            queryset = queryset.filter(
                Q(business__status=Status.PENDING) | Q(startups__status=Status.PENDING)
            ).distinct()

        page_size = 25
        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except ValueError:
            page = 1

        total = queryset.count()
        rows = queryset[(page - 1) * page_size: page * page_size]

        return Response({
            'count': total,
            'pending_profiles': User.objects.filter(
                Q(business__status=Status.PENDING) | Q(startups__status=Status.PENDING)
            ).distinct().count(),
            'page': page,
            'pages': (total + page_size - 1) // page_size,
            'results': [
                {'id': user.pk, 'full_name': user.full_name, 'email': user.email,
                 'phone': user.phone, 'role': user.role,
                 'role_display': user.get_role_display(),
                 'region_display': user.get_region_display(),
                 'initials': user.initials, 'is_verified': user.is_verified,
                 'is_admin': is_panel_admin(user),
                 'telegram_username': user.telegram_username,
                 'onboarding': onboarding_step(user),
                 'profile_status': profile_status(user),
                 'created_at': user.date_joined}
                for user in rows
            ],
        })


def profile_status(user):
    """Tadbirkor/startupper anketasining holati — ro'yxatda nishon uchun."""
    if user.role == 'entrepreneur':
        business = BusinessProfile.objects.filter(user=user).only('status').first()
        return business.status if business else None
    if user.role == 'startupper':
        startup = user.startups.only('status').first()
        return startup.status if startup else None
    return None


class PanelUserDetail(APIView):
    """Bitta foydalanuvchi: hisob, biznes yoki startap anketasi, faolligi.

    `DELETE` — hisobni butunlay o'chiradi. O'zini va bosh adminni
    o'chirib bo'lmaydi.
    """

    permission_classes = [IsPanelAdmin]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        business = BusinessProfile.objects.filter(user=user).prefetch_related('gallery').first()

        return Response({
            'user': {
                'id': user.pk, 'full_name': user.full_name, 'email': user.email,
                'phone': user.phone, 'role': user.role, 'role_display': user.get_role_display(),
                'region_display': user.get_region_display(), 'district': user.district,
                'initials': user.initials, 'is_verified': user.is_verified,
                'is_admin': is_panel_admin(user), 'is_superuser': user.is_superuser,
                'telegram_username': user.telegram_username,
                'onboarding': onboarding_step(user),
                'created_at': user.date_joined, 'last_login': user.last_login,
            },
            'business': (s.BusinessSetupSerializer(business, context={'request': request}).data
                         if business else None),
            'startups': s.StartupSetupSerializer(user.startups.all(), many=True,
                                                 context={'request': request}).data,
            'activity': {
                'initiatives': Initiative.objects.filter(author=user).count(),
                'votes': user.initiative_votes.count(),
                'solutions': Solution.objects.filter(author=user).count(),
                'events': user.event_registrations.count(),
            },
        })

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        if user.pk == request.user.pk:
            return Response({'detail': "O'zingizni o'chira olmaysiz."},
                            status=status.HTTP_400_BAD_REQUEST)
        if user.is_superuser:
            return Response({'detail': "Bosh adminni o'chirib bo'lmaydi."},
                            status=status.HTTP_400_BAD_REQUEST)

        label = user.full_name or user.email
        # Startap foydalanuvchiga `SET_NULL` bilan bog'langan — egasiz qolib
        # reyestrda yurmasin, birga o'chiriladi
        startups = user.startups.count()
        user.startups.all().delete()
        user.delete()

        return Response({'deleted': True, 'label': label, 'startups': startups})


@api_view(['POST'])
@permission_classes([IsPanelAdmin])
def moderate_profile(request, pk):
    """Tadbirkor yoki startupper anketasini tasdiqlash / rad etish.

    `status` — `approved` yoki `rejected`, `note` — rad etilganda sabab.
    Natija foydalanuvchiga bildirishnoma bo'lib boradi.
    """
    user = get_object_or_404(User, pk=pk)
    new_status = request.data.get('status')
    note = str(request.data.get('note') or '').strip()

    if new_status not in (Status.APPROVED, Status.REJECTED):
        return Response({'detail': "Holat `approved` yoki `rejected` bo'lishi kerak."},
                        status=status.HTTP_400_BAD_REQUEST)

    if user.role == 'entrepreneur':
        profile = BusinessProfile.objects.filter(user=user).first()
        kind, link = "Biznes profilingiz", "/kabinet/biznesim"
    elif user.role == 'startupper':
        profile = user.startups.first()
        kind, link = "Startap anketangiz", "/kabinet/startapim"
    else:
        profile = None

    if profile is None:
        return Response({'detail': "Bu foydalanuvchida tekshiriladigan anketa yo'q."},
                        status=status.HTTP_400_BAD_REQUEST)

    profile.status = new_status
    fields = ['status', 'updated_at']
    if hasattr(profile, 'admin_note'):
        profile.admin_note = note
        fields.append('admin_note')
    profile.save(update_fields=fields)

    approved = new_status == Status.APPROVED
    Notification.objects.create(
        user=user,
        title=f"{kind} tasdiqlandi" if approved else f"{kind} qaytarildi",
        message=("Endi u ommaviy ro'yxatda ko'rinadi." if approved
                 else (note or "Ma'lumotlarni tekshirib, qayta yuboring.")),
        type='success' if approved else 'warning',
        link=link,
    )

    return Response({'status': new_status})


@api_view(['POST'])
@permission_classes([IsPanelAdmin])
def toggle_admin(request, pk):
    """Bitta tugma bilan adminlik berish yoki olib qo'yish."""
    target = get_object_or_404(User, pk=pk)

    if target.pk == request.user.pk:
        return Response({'detail': "O'zingizning huquqingizni o'zgartira olmaysiz."},
                        status=status.HTTP_400_BAD_REQUEST)
    if target.is_superuser:
        return Response({'detail': "Bosh adminning huquqini o'zgartirib bo'lmaydi."},
                        status=status.HTTP_400_BAD_REQUEST)

    granting = not is_panel_admin(target)

    if granting:
        target.is_staff = True
        target.role = 'admin'
        target.is_verified = True
    else:
        target.is_staff = False
        target.role = 'entrepreneur'

    target.save(update_fields=['is_staff', 'role', 'is_verified'])

    Notification.objects.create(
        user=target,
        title="Adminlik huquqi berildi" if granting else "Adminlik huquqi olib qo'yildi",
        message=("Endi boshqaruv paneliga kira olasiz."
                 if granting else "Boshqaruv paneliga kirish yopildi."),
        type='info' if granting else 'warning',
    )

    return Response({'id': target.pk, 'is_admin': granting,
                     'role': target.role, 'role_display': target.get_role_display()})


@api_view(['POST'])
@permission_classes([IsPanelAdmin])
def adjust_votes(request, pk):
    """Tashabbus ovozini qo'lda o'zgartirish (PR uchun).

    `delta` — qo'shish/ayirish, `exact` — aniq qiymat qo'yish.
    Haqiqiy ovozlar jadvaliga tegilmaydi, faqat hisoblagich o'zgaradi.
    """
    initiative = get_object_or_404(Initiative, pk=pk)

    if 'exact' in request.data:
        try:
            value = max(int(request.data['exact']), 0)
        except (TypeError, ValueError):
            return Response({'detail': "Son kiriting."},
                            status=status.HTTP_400_BAD_REQUEST)
        Initiative.objects.filter(pk=pk).update(vote_count=value)
    else:
        try:
            delta = int(request.data.get('delta', 0))
        except (TypeError, ValueError):
            return Response({'detail': "Son kiriting."},
                            status=status.HTTP_400_BAD_REQUEST)
        # `vote_count` musbat maydon — ayirishda 0 dan pastga tushmasin.
        # Bazaga yozishdan oldin cheklaymiz, aks holda CHECK cheklovi buziladi.
        Initiative.objects.filter(pk=pk).update(
            vote_count=Greatest(F('vote_count') + delta, Value(0)))

    initiative.refresh_from_db(fields=['vote_count'])
    return Response({'id': initiative.pk, 'vote_count': initiative.vote_count})


# --------------------------------------------------------------------------
# Ro'yxatlar va o'chirish
# --------------------------------------------------------------------------

class PanelNews(APIView):
    """Yangiliklarni ko'rish va qo'shish.

    Rasm yuborilishi mumkin, shuning uchun JSON ham, multipart ham qabul
    qilinadi (`parser_classes`). Muallif ismi bo'sh bo'lsa — kirgan admin.
    """

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        queryset = News.objects.all().order_by('-published_at')

        search = request.query_params.get('q')
        if search:
            queryset = queryset.filter(title__icontains=search)

        category = request.query_params.get('kategoriya')
        if category:
            queryset = queryset.filter(category=category)

        rows = queryset[:60]
        return Response({
            'count': queryset.count(),
            'results': s.PanelNewsSerializer(rows, many=True,
                                             context={'request': request}).data,
        })

    def post(self, request):
        serializer = s.PanelNewsSerializer(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user,
                        author_name=(request.data.get('author_name')
                                     or request.user.full_name))
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PanelNewsDetail(APIView):
    """Bitta yangilikni tahrirlash. O'chirish umumiy `panel_delete` orqali."""

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request, pk):
        item = get_object_or_404(News, pk=pk)
        return Response(s.PanelNewsSerializer(item, context={'request': request}).data)

    def patch(self, request, pk):
        item = get_object_or_404(News, pk=pk)
        serializer = s.PanelNewsSerializer(item, data=request.data, partial=True,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PanelResource(APIView):
    """Umumiy ko'rish-qo'shish: tadbirlar va e'lonlar uchun.

    Ikkalasida ham fayl bo'lishi mumkin (rasm, hujjat), shuning uchun
    multipart ham qabul qilinadi.
    """

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    model = None
    serializer_class = None
    order = '-created_at'
    search_field = 'title'

    def get(self, request):
        queryset = self.model.objects.all().order_by(self.order)

        search = request.query_params.get('q')
        if search:
            queryset = queryset.filter(**{f"{self.search_field}__icontains": search})

        rows = queryset[:60]
        return Response({
            'count': queryset.count(),
            'results': self.serializer_class(rows, many=True,
                                             context={'request': request}).data,
        })

    def post(self, request):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PanelResourceDetail(APIView):
    """Bitta yozuvni tahrirlash. O'chirish umumiy `panel_delete` orqali."""

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    model = None
    serializer_class = None

    def patch(self, request, pk):
        item = get_object_or_404(self.model, pk=pk)
        serializer = self.serializer_class(item, data=request.data, partial=True,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PanelEvents(PanelResource):
    model = Event
    serializer_class = s.PanelEventSerializer
    order = '-starts_at'


class PanelEventDetail(PanelResourceDetail):
    model = Event
    serializer_class = s.PanelEventSerializer


class PanelAnnouncements(PanelResource):
    model = Announcement
    serializer_class = s.PanelAnnouncementSerializer
    order = '-posted_at'


class PanelAnnouncementDetail(PanelResourceDetail):
    model = Announcement
    serializer_class = s.PanelAnnouncementSerializer


class PanelImport(APIView):
    """Tashabbuslarni JSON'dan ommaviy yuklash.

    Kutilayotgan shakl (eski Django importi bilan bir xil):

        {"initiatives": [
            {"direction": "eco", "kind": "idea", "title": "...",
             "description": "...", "expected_result": "...",
             "author_name": "...", "author_phone": "...", "region": "...",
             "vote_count": 287, "created_at": "2026-05-14",
             "comments": [{"author_name": "...", "text": "...",
                           "created_at": "2026-05-20"}]}
        ]}

    Bir xil sarlavhali tashabbus bor bo'lsa — o'tkazib yuboriladi, ustiga
    yozilmaydi. Shuning uchun faylni ikki marta yuklash xavfsiz.
    """

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        payload = self._payload(request)
        if payload is None:
            return Response({'detail': "JSON o'qib bo'lmadi."},
                            status=status.HTTP_400_BAD_REQUEST)

        rows = payload.get('initiatives') if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return Response({'detail': wrong_file_message(payload, 'initiatives')},
                            status=status.HTTP_400_BAD_REQUEST)

        valid_directions = {item['id'] for item in DIRECTIONS}
        created = skipped = comments = 0
        votes = 0
        problems = []

        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                problems.append(f"{index}-yozuv: obyekt emas")
                continue

            title = (row.get('title') or '').strip()
            direction = row.get('direction')

            if not title or not row.get('description'):
                problems.append(f"{index}-yozuv: sarlavha yoki tavsif yo'q")
                continue
            if direction not in valid_directions:
                problems.append(f"{index}-yozuv: «{direction}» yo'nalishi yo'q")
                continue
            if Initiative.objects.filter(title=title, direction=direction).exists():
                skipped += 1
                continue

            initiative = Initiative.objects.create(
                direction=direction,
                kind=row.get('kind') or 'idea',
                title=title[:200],
                summary=(row.get('summary') or '')[:200],
                description=row['description'],
                expected_result=row.get('expected_result') or '',
                author_name=(row.get('author_name') or "Noma'lum")[:150],
                author_phone=(row.get('author_phone') or '')[:25],
                region=row.get('region') or '',
                vote_count=max(int(row.get('vote_count') or 0), 0),
                status=Status.APPROVED,
                is_published=True,
            )

            created += 1
            votes += initiative.vote_count

            # Sana berilgan bo'lsa — `auto_now_add`ni chetlab o'tamiz
            posted = parse_datetime_loose(row.get('created_at'))
            if posted:
                Initiative.objects.filter(pk=initiative.pk).update(created_at=posted)

            for item in row.get('comments') or []:
                if not isinstance(item, dict) or not item.get('text'):
                    continue
                comment = InitiativeComment.objects.create(
                    initiative=initiative,
                    author_name=(item.get('author_name') or "Noma'lum")[:150],
                    text=item['text'],
                    is_published=True,
                )
                comments += 1
                written = parse_datetime_loose(item.get('created_at'))
                if written:
                    InitiativeComment.objects.filter(pk=comment.pk).update(created_at=written)

        return Response({
            'created': created,
            'skipped': skipped,
            'comments': comments,
            'votes': votes,
            'problems': problems[:20],
        })

    @staticmethod
    def _payload(request):
        """JSON tanadan yoki yuklangan fayldan o'qiydi."""
        uploaded = request.FILES.get('file')
        if uploaded:
            try:
                return json.loads(uploaded.read().decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                return None

        raw = request.data.get('json') if isinstance(request.data, dict) else None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except ValueError:
                return None

        return request.data if isinstance(request.data, (dict, list)) else None


class PanelImportOrganizations(APIView):
    """Tashkilotlarni muammolari va takliflari bilan JSON'dan yuklash.

    Kutilayotgan shakl:

        {"organizations": [
            {"name": "AgroTech MChJ", "sphere": "qishloq_xojaligi",
             "contact_person": "Ali Valiyev", "phone": "+998901112233",
             "email": "info@agro.uz", "region": "samarqand", "employees": 40,
             "problems": [
                {"category": "main", "description": "...",
                 "created_at": "2026-04-02",
                 "solutions": [
                    {"author_name": "Aziz", "title": "...", "description": "...",
                     "technologies": "...", "expected_result": "...",
                     "like_count": 5, "created_at": "2026-04-10"}
                 ]}
             ]}
        ]}

    Shu nomli tashkilot bor bo'lsa yangisi yaratilmaydi — mavjudiga
    muammolar qo'shiladi. Bir xil tavsifli muammo takrorlanmaydi.
    """

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        payload = PanelImport._payload(request)
        if payload is None:
            return Response({'detail': "JSON o'qib bo'lmadi."},
                            status=status.HTTP_400_BAD_REQUEST)

        rows = payload.get('organizations') if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return Response({'detail': wrong_file_message(payload, 'organizations')},
                            status=status.HTTP_400_BAD_REQUEST)

        spheres = set(OrganizationSphere.values)
        categories = set(ProblemCategory.values)
        regions = set(Region.values)

        created = reused = problems_added = solutions_added = likes = 0
        problems = []

        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                problems.append(f"{index}-yozuv: obyekt emas")
                continue

            name = (row.get('name') or '').strip()
            if not name:
                problems.append(f"{index}-yozuv: tashkilot nomi yo'q")
                continue

            sphere = row.get('sphere') or OrganizationSphere.OTHER
            if sphere not in spheres:
                problems.append(f"«{name}»: «{sphere}» sohasi yo'q")
                continue

            region = row.get('region') or ''
            if region and region not in regions:
                problems.append(f"«{name}»: «{region}» hududi yo'q")
                region = ''

            organization = Organization.objects.filter(name=name).first()
            if organization:
                reused += 1
            else:
                organization = Organization.objects.create(
                    name=name[:200],
                    sphere=sphere,
                    contact_person=(row.get('contact_person') or "Ko'rsatilmagan")[:150],
                    phone=(row.get('phone') or '')[:25],
                    email=row.get('email') or '',
                    region=region,
                    employees=row.get('employees') or None,
                )
                created += 1

            for item in row.get('problems') or []:
                if not isinstance(item, dict):
                    continue

                description = (item.get('description') or '').strip()
                category = item.get('category') or ProblemCategory.MAIN

                if not description:
                    problems.append(f"«{name}»: tavsifsiz muammo o'tkazildi")
                    continue
                if category not in categories:
                    problems.append(f"«{name}»: «{category}» kategoriyasi yo'q")
                    continue
                if organization.problems.filter(description=description).exists():
                    continue

                problem = Problem.objects.create(
                    organization=organization,
                    category=category,
                    description=description,
                    status=Status.APPROVED,
                    is_published=True,
                )
                problems_added += 1

                posted = parse_datetime_loose(item.get('created_at'))
                if posted:
                    Problem.objects.filter(pk=problem.pk).update(created_at=posted)

                for entry in item.get('solutions') or []:
                    if not isinstance(entry, dict) or not entry.get('description'):
                        continue

                    solution = Solution.objects.create(
                        problem=problem,
                        author_name=(entry.get('author_name') or "Noma'lum")[:150],
                        title=(entry.get('title') or "Taklif")[:200],
                        description=entry['description'],
                        technologies=(entry.get('technologies') or '')[:300],
                        expected_result=entry.get('expected_result') or '',
                        like_count=max(int(entry.get('like_count') or 0), 0),
                        status=Status.APPROVED,
                    )
                    solutions_added += 1
                    likes += solution.like_count

                    written = parse_datetime_loose(entry.get('created_at'))
                    if written:
                        Solution.objects.filter(pk=solution.pk).update(created_at=written)

        return Response({
            'created': created,
            'reused': reused,
            'problems_added': problems_added,
            'solutions': solutions_added,
            'likes': likes,
            'issues': problems[:20],
        })


#: Import bo'limlarining nomi — xato xabarida ishlatiladi
IMPORT_SECTIONS = {
    'initiatives': "Tashabbuslar",
    'organizations': "Tashkilotlar",
}


def wrong_file_message(payload, expected):
    """Fayl noto'g'ri bo'limga tashlanganini aniqlab, aniq xabar beradi.

    Eng ko'p uchraydigan xato — tashabbuslar faylini tashkilotlar
    bo'limiga tashlash. «ro'yxat topilmadi» deyish o'rniga qaysi bo'limga
    yuklash kerakligini aytamiz.
    """
    if isinstance(payload, dict):
        for key, label in IMPORT_SECTIONS.items():
            if key != expected and isinstance(payload.get(key), list):
                return (f"Bu «{label}» fayli — uni «{label}» bo'limiga yuklang.")

    expected_label = IMPORT_SECTIONS.get(expected, expected)
    return (f"Faylda `{expected}` ro'yxati topilmadi. «{expected_label}» bo'limi uchun "
            f"fayl ildizida `{expected}` bo'lishi kerak.")


def parse_datetime_loose(value):
    """`2026-05-14` ham, to'liq ISO ham bo'lishi mumkin. Bo'lmasa — `None`."""
    if not value or not isinstance(value, str):
        return None

    moment = parse_datetime(value)
    if moment is None:
        day = parse_date(value)
        if day is None:
            return None
        moment = datetime.combine(day, time(12, 0))

    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment


#: Har bir bo'limda ko'rinishni boshqaradigan maydon nomi
VISIBILITY = {
    'news': 'is_published',
    'events': 'is_published',
    'announcements': 'is_active',
    'initiatives': 'is_published',
    'problems': 'is_published',
    'peers': 'is_published',
    'startups': 'is_public',
}

#: Moderatsiya holati bor bo'limlar
MODERATED = {'initiatives', 'problems', 'peers', 'startups'}


@api_view(['POST'])
@permission_classes([IsPanelAdmin])
def panel_moderate(request, resource, pk):
    """Yozuvni tasdiqlash/rad etish va ko'rinishini yoqib-o'chirish.

    `status` — `approved` yoki `rejected` (faqat moderatsiyali bo'limlarda),
    `visible` — saytda ko'rinsinmi. Ikkalasini birga yuborish ham mumkin.
    """
    if resource not in MODELS:
        raise Http404

    model, serializer = MODELS[resource]
    item = get_object_or_404(model, pk=pk)
    changed = []

    new_status = request.data.get('status')
    if new_status is not None:
        if resource not in MODERATED:
            return Response({'detail': "Bu bo'limda holat yo'q."},
                            status=status.HTTP_400_BAD_REQUEST)
        if new_status not in Status.values:
            return Response({'detail': "Noma'lum holat."},
                            status=status.HTTP_400_BAD_REQUEST)
        item.status = new_status
        changed.append('status')

    visible = request.data.get('visible')
    if visible is not None:
        field = VISIBILITY.get(resource)
        if not field:
            return Response({'detail': "Bu bo'limda ko'rinish sozlanmaydi."},
                            status=status.HTTP_400_BAD_REQUEST)
        setattr(item, field, bool(visible))
        changed.append(field)

    if not changed:
        return Response({'detail': "O'zgartirish uchun maydon yuborilmadi."},
                        status=status.HTTP_400_BAD_REQUEST)

    item.save(update_fields=changed + ['updated_at'])
    return Response(serializer(item, context={'request': request}).data)


MODELS = {
    'news': (News, s.PanelNewsSerializer),
    'events': (Event, s.EventListSerializer),
    'announcements': (Announcement, s.AnnouncementSerializer),
    'initiatives': (Initiative, s.InitiativeListSerializer),
    'problems': (Problem, s.ProblemSerializer),
    'peers': (Peer, s.PeerSerializer),
    'startups': (Startup, s.StartupSerializer),
}


class PanelList(APIView):
    permission_classes = [IsPanelAdmin]

    def get(self, request, resource):
        if resource not in MODELS:
            raise Http404

        model, serializer = MODELS[resource]
        queryset = model.objects.all()

        search = request.query_params.get('q')
        if search:
            field = 'name' if resource in ('peers', 'startups') else 'title'
            if resource == 'problems':
                field = 'description'
            if resource == 'peers':
                field = 'full_name'
            queryset = queryset.filter(**{f"{field}__icontains": search})

        rows = list(queryset[:60])
        data = serializer(rows, many=True, context={'request': request}).data

        # Panelga moderatsiya uchun ikkita qo'shimcha maydon kerak:
        # holat va saytda ko'rinishi. Ochiq serializerlarni o'zgartirmaymiz.
        field = VISIBILITY.get(resource)
        for row, obj in zip(data, rows):
            row['status'] = getattr(obj, 'status', None)
            row['visible'] = bool(getattr(obj, field, True)) if field else True

        return Response({'count': queryset.count(), 'results': data})


@api_view(['DELETE'])
@permission_classes([IsPanelAdmin])
def panel_delete(request, resource, pk):
    """Yozuvni o'chirish — panel ro'yxatlaridagi savatcha tugmasi."""
    if resource not in MODELS:
        raise Http404

    model, _ = MODELS[resource]
    obj = get_object_or_404(model, pk=pk)
    label = str(obj)
    obj.delete()

    return Response({'deleted': True, 'label': label})


# --------------------------------------------------------------------------
# Tashkilotlar — kiritish va login/parol berish
# --------------------------------------------------------------------------

def _generate_password(length=12):
    """O'qish oson, lekin taxmin qilish qiyin parol.

    Chalkashadigan belgilar (0/O, 1/l/I) chiqarib tashlangan — parolni
    telefonda aytib berish yoki qog'ozga yozish oson bo'lsin.
    """
    alphabet = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class PanelOrganizations(APIView):
    """Tashkilotlar ro'yxati va yangisini kiritish."""

    permission_classes = [IsPanelAdmin]

    def get(self, request):
        queryset = Organization.objects.select_related('user').order_by('-created_at')

        search = request.query_params.get('q')
        if search:
            queryset = queryset.filter(name__icontains=search)

        return Response({
            'count': queryset.count(),
            'results': [
                {
                    'id': org.pk,
                    'name': org.name,
                    'sphere': org.sphere,
                    'sphere_display': org.get_sphere_display(),
                    'contact_person': org.contact_person,
                    'phone': org.phone,
                    'email': org.email,
                    'region_display': org.get_region_display(),
                    'employees': org.employees,
                    'problem_count': org.problems.count(),
                    # Hisob ochilganmi — parol qayta yaratish uchun kerak
                    'account_email': org.user.email if org.user else None,
                    'created_at': org.created_at,
                }
                for org in queryset[:100]
            ],
        })

    def post(self, request):
        """Tashkilotni kiritadi va unga kirish hisobini ochadi.

        Parol faqat shu javobda bir marta ko'rsatiladi — bazada
        faqat xesh saqlanadi, keyin uni qayta ko'rib bo'lmaydi.
        """
        data = request.data
        name = str(data.get('name', '')).strip()
        email = str(data.get('email', '')).strip().lower()

        if not name:
            return Response({'detail': "Tashkilot nomini kiriting."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not email:
            return Response({'detail': "Login uchun email kiriting."},
                            status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=email).exists():
            return Response({'detail': "Bu email allaqachon band."},
                            status=status.HTTP_400_BAD_REQUEST)

        password = _generate_password()

        account = User.objects.create_user(
            email=email,
            password=password,
            full_name=str(data.get('contact_person', '')).strip() or name,
            phone=str(data.get('phone', '')).strip(),
            role='organization',
            region=str(data.get('region', '')).strip(),
            is_verified=True,
        )

        organization = Organization.objects.create(
            user=account,
            name=name,
            sphere=str(data.get('sphere', '')).strip() or 'boshqa',
            contact_person=str(data.get('contact_person', '')).strip() or name,
            phone=str(data.get('phone', '')).strip(),
            email=email,
            region=str(data.get('region', '')).strip(),
            employees=data.get('employees') or None,
        )

        return Response({
            'id': organization.pk,
            'name': organization.name,
            'credentials': {'email': email, 'password': password},
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsPanelAdmin])
def reset_organization_password(request, pk):
    """Tashkilot parolini qaytadan yaratadi (eskisi bekor bo'ladi)."""
    organization = get_object_or_404(Organization, pk=pk)

    if organization.user is None:
        return Response({'detail': "Bu tashkilotda kirish hisobi yo'q."},
                        status=status.HTTP_400_BAD_REQUEST)

    password = _generate_password()
    organization.user.set_password(password)
    organization.user.save(update_fields=['password'])

    return Response({
        'id': organization.pk,
        'credentials': {'email': organization.user.email, 'password': password},
    })
