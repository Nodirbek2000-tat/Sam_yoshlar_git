"""Next.js frontend uchun REST API (`/api/v1/`).

Ko'rish hamma uchun ochiq. Ovoz berish, taklif yozish, tadbirga yozilish va
tashabbus bildirish uchun JWT bilan kirish talab qilinadi.
"""
from django.db.models import Count, F, Q, Sum, Value
from django.db.models.functions import Greatest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.abroad.models import Peer
from apps.accounts.models import Role
from apps.cabinet.models import Notification
from apps.content.models import (Announcement, AnnouncementType, Event,
                                 EventRegistration, News, NewsCategory)
from apps.core.constants import Region, Status
from apps.initiatives.directions import DIRECTIONS, MILESTONES, get_direction, random_cheer
from apps.initiatives.models import (PROBLEM_QUESTIONS, Initiative, InitiativeComment,
                                     InitiativeVote, Problem, ProblemCategory,
                                     Solution, SolutionLike)
from apps.business.models import BusinessProfile, BusinessSphere
from apps.startups.models import Startup, StartupSphere, StartupStage

from . import serializers as s


# --------------------------------------------------------------------------
# Yordamchilar
# --------------------------------------------------------------------------

def voted_ids(request, queryset):
    """Foydalanuvchi qaysi tashabbuslarga ovoz berganini bir so'rovda oladi."""
    user = request.user
    if not user.is_authenticated:
        return set()
    ids = [item.pk for item in queryset]
    if not ids:
        return set()
    return set(InitiativeVote.objects
               .filter(initiative_id__in=ids, user=user)
               .values_list('initiative_id', flat=True))


class VotedContextMixin:
    """Ro'yxatdagi tashabbuslar uchun `voted` bayrog'ini kontekstga qo'shadi."""

    def get_serializer_context(self):
        context = super().get_serializer_context()
        page = getattr(self, '_page_objects', None)
        if page is not None:
            context['voted_ids'] = voted_ids(self.request, page)
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        self._page_objects = page if page is not None else list(queryset)
        serializer = self.get_serializer(self._page_objects, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


# --------------------------------------------------------------------------
# Yangiliklar, tadbirlar, e'lonlar
# --------------------------------------------------------------------------

class NewsList(generics.ListAPIView):
    serializer_class = s.NewsListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = News.objects.published()
        category = self.request.query_params.get('kategoriya')
        if category:
            queryset = queryset.filter(category=category)
        search = self.request.query_params.get('q')
        if search:
            queryset = queryset.filter(title__icontains=search)
        return queryset


class NewsDetail(generics.RetrieveAPIView):
    serializer_class = s.NewsDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    queryset = News.objects.published()

    def retrieve(self, request, *args, **kwargs):
        item = self.get_object()
        News.objects.filter(pk=item.pk).update(views=F('views') + 1)
        item.refresh_from_db(fields=['views'])
        return Response(self.get_serializer(item).data)


class EventList(generics.ListAPIView):
    serializer_class = s.EventListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Event.objects.published()
        when = self.request.query_params.get('holat')
        now = timezone.now()
        if when == 'kelgusi':
            queryset = queryset.filter(starts_at__gte=now).order_by('starts_at')
        elif when == 'otgan':
            queryset = queryset.filter(starts_at__lt=now).order_by('-starts_at')
        return queryset


class EventDetail(generics.RetrieveAPIView):
    serializer_class = s.EventDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    queryset = Event.objects.published()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def event_register(request, slug):
    """Tadbirga yozilish yoki bekor qilish — bitta tugma."""
    event = get_object_or_404(Event.objects.published(), slug=slug)

    if event.is_past:
        return Response({'detail': "Bu tadbir allaqachon o'tib ketgan."},
                        status=status.HTTP_400_BAD_REQUEST)

    registration = EventRegistration.objects.filter(event=event, user=request.user).first()

    if registration and not registration.is_cancelled:
        registration.is_cancelled = True
        registration.save(update_fields=['is_cancelled', 'updated_at'])
        return Response({'registered': False, 'detail': "Ishtirokingiz bekor qilindi.",
                         'seats_left': event.seats_left})

    if event.is_full:
        return Response({'detail': "Afsuski, joylar tugagan."},
                        status=status.HTTP_400_BAD_REQUEST)

    if registration:
        registration.is_cancelled = False
        registration.save(update_fields=['is_cancelled', 'updated_at'])
    else:
        EventRegistration.objects.create(event=event, user=request.user)

    return Response({'registered': True,
                     'detail': f"«{event.title}» tadbiriga yozildingiz!",
                     'seats_left': event.seats_left})


class AnnouncementList(generics.ListAPIView):
    serializer_class = s.AnnouncementSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Announcement.objects.filter(is_active=True)
        kind = self.request.query_params.get('turi')
        if kind:
            queryset = queryset.filter(type=kind)
        return queryset


class AnnouncementDetail(generics.RetrieveAPIView):
    serializer_class = s.AnnouncementSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    queryset = Announcement.objects.filter(is_active=True)


# --------------------------------------------------------------------------
# Tashabbuslar
# --------------------------------------------------------------------------

class DirectionList(APIView):
    """14 yo'nalish + har birining jonli statistikasi."""

    permission_classes = [AllowAny]

    def get(self, request):
        rows = (Initiative.objects.filter(is_published=True)
                .values('direction')
                .annotate(votes=Sum('vote_count'), ideas=Count('id')))
        stats = {row['direction']: row for row in rows}

        data = []
        for item in DIRECTIONS:
            row = stats.get(item['id'], {})
            data.append({**item,
                         'votes': row.get('votes') or 0,
                         'ideas': row.get('ideas') or 0})
        return Response(data)


class InitiativeList(VotedContextMixin, generics.ListCreateAPIView):
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        return (s.InitiativeCreateSerializer if self.request.method == 'POST'
                else s.InitiativeListSerializer)

    def get_permissions(self):
        # Tashabbus bildirish uchun ro'yxatdan o'tish kerak
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        queryset = (Initiative.objects
                    .filter(is_published=True, status=Status.APPROVED)
                    .annotate(comment_total=Count('comments', distinct=True)))

        direction = self.request.query_params.get('yonalish')
        if direction:
            queryset = queryset.filter(direction=direction)

        kind = self.request.query_params.get('turi')
        if kind:
            queryset = queryset.filter(kind=kind)

        region = self.request.query_params.get('hudud')
        if region:
            queryset = queryset.filter(region=region)

        search = self.request.query_params.get('q')
        if search:
            queryset = queryset.filter(title__icontains=search)

        ordering = self.request.query_params.get('tartib')
        if ordering == 'yangi':
            return queryset.order_by('-created_at')
        return queryset.order_by('-vote_count', '-created_at')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, status=Status.APPROVED,
                        is_published=True)


class InitiativeDetail(generics.RetrieveAPIView):
    serializer_class = s.InitiativeListSerializer
    permission_classes = [AllowAny]
    queryset = (Initiative.objects.filter(is_published=True)
                .annotate(comment_total=Count('comments', distinct=True)))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['voted_ids'] = voted_ids(self.request, [self.get_object()])
        return context

    def retrieve(self, request, *args, **kwargs):
        initiative = self.get_object()
        data = self.get_serializer(initiative).data
        data['rank'] = initiative.rank
        data['comments'] = s.InitiativeCommentSerializer(
            initiative.comments.filter(is_published=True).order_by('-created_at'),
            many=True).data
        data['siblings'] = s.InitiativeListSerializer(
            Initiative.objects.filter(direction=initiative.direction, is_published=True)
            .exclude(pk=initiative.pk).order_by('-vote_count')[:4],
            many=True, context=self.get_serializer_context()).data
        return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiative_vote(request, pk):
    """Ovoz berish — bir kishi bir marta."""
    initiative = get_object_or_404(Initiative, pk=pk, is_published=True)

    if InitiativeVote.objects.filter(initiative=initiative, user=request.user).exists():
        return Response({'detail': "Siz bu tashabbusga allaqachon ovoz bergansiz.",
                         'votes': initiative.vote_count},
                        status=status.HTTP_409_CONFLICT)

    InitiativeVote.objects.create(initiative=initiative, user=request.user, session_key='')
    Initiative.objects.filter(pk=initiative.pk).update(vote_count=F('vote_count') + 1)
    initiative.refresh_from_db(fields=['vote_count'])

    milestone = initiative.vote_count in MILESTONES

    if initiative.author_id and milestone:
        Notification.objects.create(
            user=initiative.author,
            title=f"Tashabbusingiz {initiative.vote_count} ta ovoz to'pladi!",
            message=initiative.title,
            type='success',
            link=f"/tashabbuslar/{initiative.pk}",
        )

    direction_votes = (Initiative.objects
                       .filter(direction=initiative.direction, is_published=True)
                       .aggregate(total=Sum('vote_count'))['total'] or 0)

    return Response({
        'votes': initiative.vote_count,
        'rank': initiative.rank,
        'direction': initiative.direction,
        'direction_votes': direction_votes,
        'milestone': milestone,
        'message': MILESTONES.get(initiative.vote_count) or random_cheer(),
    })


class InitiativeComments(generics.ListCreateAPIView):
    serializer_class = s.InitiativeCommentSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_initiative(self):
        return get_object_or_404(Initiative, pk=self.kwargs['pk'], is_published=True)

    def get_queryset(self):
        return (self.get_initiative().comments
                .filter(is_published=True).order_by('-created_at'))

    def perform_create(self, serializer):
        initiative = self.get_initiative()
        comment = serializer.save(initiative=initiative, author=self.request.user)

        if initiative.author_id and initiative.author_id != self.request.user.pk:
            Notification.objects.create(
                user=initiative.author,
                title="Tashabbusingizga yangi taklif",
                message=f"«{initiative.title}» — {comment.author_label}: {comment.text[:90]}",
                type='info',
                link=f"/tashabbuslar/{initiative.pk}",
            )


# --------------------------------------------------------------------------
# Tashkilot muammolari
# --------------------------------------------------------------------------

class ProblemList(generics.ListAPIView):
    serializer_class = s.ProblemSerializer
    permission_classes = [AllowAny]
    queryset = (Problem.objects.filter(is_published=True)
                .select_related('organization')
                .annotate(solution_total=Count('solutions'))
                .order_by('-created_at'))


class ProblemDetail(generics.RetrieveAPIView):
    serializer_class = s.ProblemSerializer
    permission_classes = [AllowAny]
    queryset = (Problem.objects.filter(is_published=True)
                .select_related('organization')
                .annotate(solution_total=Count('solutions')))

    def retrieve(self, request, *args, **kwargs):
        problem = self.get_object()
        data = self.get_serializer(problem).data
        # Ko'p layk yig'gani birinchi turadi
        solutions = list(problem.solutions.filter(status=Status.APPROVED)
                         .order_by('-like_count', '-created_at'))
        data['solutions'] = s.SolutionSerializer(
            solutions, many=True,
            context={'liked_ids': liked_solution_ids(request, solutions)}).data
        return Response(data)


class IsOrganization(BasePermission):
    """Muammo yozishga faqat tashkilot hisobi haqli.

    Tadbirkor, startupper va oddiy foydalanuvchi tashabbus bildiradi;
    muammoni esa tashkilotning o'zi yozadi va yoshlar unga yechim taklif
    qiladi. Shuning uchun bu yerda rol aniq tekshiriladi.
    """

    message = ("Muammo yozish faqat tashkilot hisobiga ochiq. "
               "Tashkilot bo'lsangiz, kengashga murojaat qiling — sizga login beriladi.")

    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.role == Role.ORGANIZATION
                    and user.organizations.exists())


class ProblemCreate(generics.CreateAPIView):
    """Tashkilot o'z muammosini yozadi.

    Anketa savollaridan bittasi tanlanadi (`category`) va unga javob
    yoziladi. Yozilishi bilan yoshlarga ochiladi — moderatsiya kutmaydi,
    chunki muallif allaqachon tasdiqlangan tashkilot.
    """

    serializer_class = s.ProblemCreateSerializer
    permission_classes = [IsOrganization]

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organizations.first(),
            status=Status.APPROVED,
            is_published=True,
        )


class MyProblems(APIView):
    """Tashkilotning o'z muammolari va ularga kelgan takliflar."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        organizations = list(request.user.organizations.all())
        if not organizations:
            return Response({'is_organization': False, 'count': 0, 'results': []})

        queryset = (Problem.objects
                    .filter(organization__in=organizations)
                    .select_related('organization')
                    .annotate(solution_total=Count('solutions'))
                    .order_by('-created_at'))

        rows = []
        for problem in queryset:
            data = s.ProblemSerializer(problem, context={'request': request}).data
            solutions = list(problem.solutions.filter(status=Status.APPROVED)
                             .order_by('-like_count', '-created_at'))
            data['solutions'] = s.SolutionSerializer(
                solutions, many=True,
                context={'liked_ids': liked_solution_ids(request, solutions)}).data
            rows.append(data)

        return Response({
            'is_organization': True,
            'count': len(rows),
            'results': rows,
        })


class ProblemSolutions(generics.CreateAPIView):
    serializer_class = s.SolutionSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        problem = get_object_or_404(Problem, pk=self.kwargs['pk'], is_published=True)

        # Taklif darhol ko'rinadi — tashabbuslar bilan bir xil tartib.
        # Nomaqbul bo'lsa admin panelidan yashiradi yoki o'chiradi.
        solution = serializer.save(problem=problem, author=self.request.user,
                                   author_name=self.request.user.full_name
                                   or self.request.user.get_username(),
                                   status=Status.APPROVED)

        # Tashkilot egasiga xabar bersin. Hisobi bo'lmagan tashkilot ham
        # bo'ladi (import qilinganlar) — u holda xabar yuborilmaydi,
        # taklif baribir muammo sahifasida va panelda ko'rinadi.
        owner = problem.organization.user
        if owner:
            Notification.objects.create(
                user=owner,
                title="Muammoingizga yangi taklif keldi",
                message=f"«{problem.get_category_display()}» — {solution.title}",
                type='info',
                link="/kabinet/muammolarim",
            )


def liked_solution_ids(request, solutions):
    """Shu foydalanuvchi qaysi takliflarni layk qilgan — bitta so'rovda."""
    if not request.user.is_authenticated or not solutions:
        return set()
    return set(SolutionLike.objects
               .filter(user=request.user, solution__in=[item.pk for item in solutions])
               .values_list('solution_id', flat=True))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def solution_like(request, pk):
    """Taklifga layk qo'yish yoki olib tashlash (bir bosishda ikkalasi ham)."""
    solution = get_object_or_404(Solution, pk=pk, status=Status.APPROVED,
                                 problem__is_published=True)

    like = SolutionLike.objects.filter(solution=solution, user=request.user).first()
    if like:
        like.delete()
        Solution.objects.filter(pk=solution.pk).update(
            like_count=Greatest(F('like_count') - 1, Value(0)))
        liked = False
    else:
        SolutionLike.objects.create(solution=solution, user=request.user)
        Solution.objects.filter(pk=solution.pk).update(like_count=F('like_count') + 1)
        liked = True

        # Taklif egasiga xabar — o'ziga o'zi layk bosgani bundan mustasno
        if solution.author_id and solution.author_id != request.user.pk:
            Notification.objects.create(
                user=solution.author,
                title="Taklifingiz yoqdi",
                message=solution.title,
                type='success',
                link=f"/tashabbuslar/muammolar/{solution.problem_id}",
            )

    solution.refresh_from_db(fields=['like_count'])
    return Response({'liked': liked, 'like_count': solution.like_count})


# --------------------------------------------------------------------------
# Chet eldagi tengdoshlar, startaplar
# --------------------------------------------------------------------------

class PeerList(generics.ListAPIView):
    serializer_class = s.PeerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Peer.objects.filter(is_published=True, status=Status.APPROVED)
        country = self.request.query_params.get('davlat')
        if country:
            queryset = queryset.filter(country=country)
        purpose = self.request.query_params.get('maqsad')
        if purpose:
            queryset = queryset.filter(purpose=purpose)
        return queryset


class PeerDetail(generics.RetrieveAPIView):
    serializer_class = s.PeerSerializer
    permission_classes = [AllowAny]
    queryset = Peer.objects.filter(is_published=True, status=Status.APPROVED)


def public_startups():
    """Saytda faqat kengash tasdiqlagan va yashirilmagan startaplar."""
    return Startup.objects.filter(is_public=True, status=Status.APPROVED)


def public_businesses():
    return (BusinessProfile.objects.filter(is_public=True, status=Status.APPROVED)
            .select_related('user').prefetch_related('gallery'))


class StartupList(generics.ListAPIView):
    """Startaplar ro'yxati: `?soha=`, `?bosqich=`, `?q=` bilan filtrlanadi."""

    serializer_class = s.PublicStartupSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = public_startups().order_by('-created_at')
        params = self.request.query_params

        if params.get('soha'):
            queryset = queryset.filter(sphere=params['soha'])
        if params.get('bosqich'):
            queryset = queryset.filter(stage=params['bosqich'])
        if params.get('q'):
            queryset = queryset.filter(Q(name__icontains=params['q'])
                                       | Q(about__icontains=params['q']))
        return queryset


class StartupDetail(generics.RetrieveAPIView):
    serializer_class = s.PublicStartupDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return public_startups()


class BusinessList(generics.ListAPIView):
    """Tadbirkorlar ro'yxati: `?soha=`, `?hudud=`, `?q=` bilan filtrlanadi."""

    serializer_class = s.PublicBusinessSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = public_businesses().order_by('-created_at')
        params = self.request.query_params

        if params.get('soha'):
            queryset = queryset.filter(sphere=params['soha'])
        if params.get('hudud'):
            queryset = queryset.filter(region=params['hudud'])
        if params.get('q'):
            queryset = queryset.filter(Q(name__icontains=params['q'])
                                       | Q(description__icontains=params['q']))
        return queryset


class BusinessDetail(generics.RetrieveAPIView):
    serializer_class = s.PublicBusinessDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return public_businesses()


# --------------------------------------------------------------------------
# Umumiy ma'lumot — bosh sahifa uchun
# --------------------------------------------------------------------------

class Overview(APIView):
    """Bosh sahifa bir so'rovda hamma kerakli narsani oladi."""

    permission_classes = [AllowAny]

    def get(self, request):
        now = timezone.now()
        context = {'request': request}

        top = list(Initiative.objects.filter(is_published=True)
                   .annotate(comment_total=Count('comments', distinct=True))
                   .order_by('-vote_count')[:5])

        return Response({
            'stats': {
                'initiatives': Initiative.objects.filter(is_published=True).count(),
                'votes': Initiative.objects.aggregate(t=Sum('vote_count'))['t'] or 0,
                'problems': Problem.objects.filter(is_published=True).count(),
                'solutions': Solution.objects.count(),
                'peers': Peer.objects.filter(is_published=True).count(),
                'events': Event.objects.published().filter(starts_at__gte=now).count(),
                'businesses': public_businesses().count(),
                'startups': public_startups().count(),
            },
            'top_initiatives': s.InitiativeListSerializer(
                top, many=True,
                context={**context, 'voted_ids': voted_ids(request, top)}).data,
            'latest_news': s.NewsListSerializer(
                News.objects.published()[:3], many=True, context=context).data,
            'upcoming_events': s.EventListSerializer(
                Event.objects.published().filter(starts_at__gte=now).order_by('starts_at')[:3],
                many=True, context=context).data,
            'announcements': s.AnnouncementSerializer(
                Announcement.objects.filter(is_active=True).order_by('-posted_at')[:4],
                many=True, context=context).data,
            'peers': s.PeerSerializer(
                Peer.objects.filter(is_published=True, status=Status.APPROVED)
                .order_by('-created_at')[:4],
                many=True, context=context).data,
            'businesses': s.PublicBusinessSerializer(
                public_businesses().order_by('-created_at')[:3],
                many=True, context=context).data,
            'startups': s.PublicStartupSerializer(
                public_startups().order_by('-created_at')[:4],
                many=True, context=context).data,
            'open_problems': s.ProblemSerializer(
                Problem.objects.filter(is_published=True).select_related('organization')
                .annotate(solution_total=Count('solutions')).order_by('-created_at')[:3],
                many=True, context=context).data,
        })


class ReferenceData(APIView):
    """Formalar uchun ro'yxatlar: hududlar, rollar, davlatlar."""

    permission_classes = [AllowAny]

    def get(self, request):
        from apps.abroad.countries import COUNTRIES
        from apps.abroad.models import PeerPurpose
        from apps.accounts.models import Role
        from apps.cabinet.models import AppealCategory
        from apps.initiatives.models import InitiativeKind, OrganizationSphere

        def choices(source):
            return [{'value': value, 'label': label} for value, label in source]

        return Response({
            'regions': choices(Region.choices),
            # Tashkilot va admin hisobini biz o'zimiz beramiz — ro'yxatda ko'rinmaydi
            'roles': [row for row in choices(Role.choices)
                      if row['value'] not in {Role.ADMIN, Role.ORGANIZATION}],
            # Panelda filtrlash uchun — hamma rol
            'all_roles': choices(Role.choices),
            'initiative_kinds': choices(InitiativeKind.choices),
            'news_categories': choices(NewsCategory.choices),
            'startup_spheres': choices(StartupSphere.choices),
            'startup_stages': choices(StartupStage.choices),
            'business_spheres': choices(BusinessSphere.choices),
            # Tashkilot anketasining 10 savoli — muammo yozish formasi uchun
            'problem_questions': [
                {'value': item['category'], 'label': item['question'],
                 'number': item['number'], 'icon': item['icon'],
                 'short': ProblemCategory(item['category']).label}
                for item in PROBLEM_QUESTIONS
            ],
            'announcement_types': choices(AnnouncementType.choices),
            'organization_spheres': choices(OrganizationSphere.choices),
            'appeal_categories': choices(AppealCategory.choices),
            'peer_purposes': choices(PeerPurpose.choices),
            'countries': [{'value': code, 'label': name, 'short': short, 'color': color}
                          for code, name, short, color in COUNTRIES],
        })
