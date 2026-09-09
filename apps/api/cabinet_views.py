"""Shaxsiy kabinet uchun API (`/api/v1/me/`).

Hammasi joriy foydalanuvchiga tegishli — boshqa birovning ma'lumoti
hech qachon qaytmaydi, chunki har bir so'rov `request.user` bo'yicha filtrlanadi.
"""
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cabinet.models import Appeal, Notification, Suggestion
from apps.content.models import EventRegistration
from apps.core.constants import Status
from apps.initiatives.models import Initiative, InitiativeComment, Solution

from . import serializers as s


class AppealSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Appeal
        fields = ['id', 'subject', 'category', 'category_display', 'message',
                  'status', 'status_display', 'response', 'responded_at', 'created_at']
        read_only_fields = ['id', 'status', 'response', 'responded_at', 'created_at']


class SuggestionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Suggestion
        fields = ['id', 'title', 'description', 'expected_benefit',
                  'status', 'status_display', 'response', 'votes', 'created_at']
        read_only_fields = ['id', 'status', 'response', 'votes', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'type', 'type_display',
                  'link', 'is_read', 'created_at']


class CabinetOverview(APIView):
    """Kabinet yon menyusi uchun raqamlar va qisqacha holat."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        upcoming = (EventRegistration.objects
                    .filter(user=user, is_cancelled=False, event__starts_at__gte=now)
                    .count())

        return Response({
            'counts': {
                'initiatives': Initiative.objects.filter(author=user).count(),
                'events': upcoming,
                'comments': InitiativeComment.objects.filter(author=user).count(),
                'solutions': Solution.objects.filter(author=user).count(),
                'appeals': Appeal.objects.filter(user=user).count(),
                'suggestions': Suggestion.objects.filter(user=user).count(),
                'unread': Notification.objects.filter(user=user, is_read=False).count(),
            },
            # Foydalanuvchi tashabbuslari qancha ovoz to'plagan — eng yoqimli raqam
            'total_votes': sum(
                Initiative.objects.filter(author=user).values_list('vote_count', flat=True)
            ),
        })


class MyInitiatives(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = (Initiative.objects.filter(author=request.user)
                    .annotate(comment_total=Count('comments', distinct=True))
                    .order_by('-created_at'))

        rows = s.InitiativeListSerializer(
            queryset, many=True, context={'request': request}).data

        # Har birining umumiy reytingdagi o'rni
        for row, item in zip(rows, queryset):
            row['rank'] = item.rank

        return Response({'count': len(rows), 'results': rows})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_initiative(request, pk):
    """Faqat o'z tashabbusini o'chira oladi."""
    initiative = get_object_or_404(Initiative, pk=pk, author=request.user)
    initiative.delete()
    return Response({'deleted': True})


class MyEvents(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        registrations = (EventRegistration.objects
                         .filter(user=request.user, is_cancelled=False)
                         .select_related('event')
                         .order_by('-event__starts_at'))

        now = timezone.now()
        return Response({
            'count': registrations.count(),
            'results': [
                {
                    **s.EventListSerializer(row.event, context={'request': request}).data,
                    'registered_at': row.created_at,
                    'is_upcoming': row.event.starts_at >= now,
                }
                for row in registrations
            ],
        })


class MyComments(APIView):
    """Foydalanuvchi tashabbuslarga yozgan takliflari."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        comments = (InitiativeComment.objects
                    .filter(author=request.user)
                    .select_related('initiative')
                    .order_by('-created_at'))

        return Response({
            'count': comments.count(),
            'results': [
                {
                    'id': comment.pk,
                    'text': comment.text,
                    'created_at': comment.created_at,
                    'initiative': {
                        'id': comment.initiative_id,
                        'title': comment.initiative.title,
                        'vote_count': comment.initiative.vote_count,
                    },
                }
                for comment in comments
            ],
        })


class MyNotifications(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Notification.objects.filter(user=request.user).order_by('-created_at')
        return Response({
            'count': queryset.count(),
            'unread': queryset.filter(is_read=False).count(),
            'results': NotificationSerializer(queryset[:80], many=True).data,
        })

    def post(self, request):
        """Hammasini o'qilgan deb belgilaydi."""
        updated = (Notification.objects
                   .filter(user=request.user, is_read=False)
                   .update(is_read=True))
        return Response({'marked': updated})


class MyAppeals(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Appeal.objects.filter(user=request.user).order_by('-created_at')
        return Response({
            'count': queryset.count(),
            'results': AppealSerializer(queryset, many=True).data,
        })

    def post(self, request):
        serializer = AppealSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, status=Status.PENDING)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MySuggestions(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Suggestion.objects.filter(user=request.user).order_by('-created_at')
        return Response({
            'count': queryset.count(),
            'results': SuggestionSerializer(queryset, many=True).data,
        })

    def post(self, request):
        serializer = SuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, status=Status.PENDING)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyStartup(APIView):
    """Startupperning startapi — ro'yxatdan keyingi ikkinchi qadam.

    Bitta foydalanuvchida bir nechta startap bo'lishi mumkin, lekin
    ro'yxatdan o'tishda birinchisi to'ldiriladi: bor bo'lsa yangilanadi,
    bo'lmasa yaratiladi.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        startup = request.user.startups.first()
        return Response(s.StartupSetupSerializer(startup).data if startup else {})

    def post(self, request):
        startup = request.user.startups.first()
        serializer = s.StartupSetupSerializer(startup, data=request.data, partial=bool(startup))
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user,
                        full_name=request.user.full_name,
                        phone=request.user.phone,
                        email=request.user.email,
                        region=request.user.region)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyBusiness(APIView):
    """Tadbirkorning biznes profili. Foydalanuvchida bittasi bo'ladi."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, 'business', None)
        return Response(s.BusinessSetupSerializer(profile).data if profile else {})

    def post(self, request):
        profile = getattr(request.user, 'business', None)
        serializer = s.BusinessSetupSerializer(profile, data=request.data, partial=bool(profile))
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user,
                        region=request.user.region,
                        phone=request.user.phone,
                        email=request.user.email)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
