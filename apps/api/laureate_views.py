"""«Mirzo Ulug'bek vorislari» — Samarqand viloyati Innovatsion rivojlanish bo'linmasi.

Sayt: g'oliblar ro'yxati (yil bo'yicha saralash) va har birining sahifasi.
Panel: Excel'dan yuklash va tahrirlash; yashirish va o'chirish umumiy
`panel_moderate` / `panel_delete` orqali.
"""

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.startups.laureate_import import import_workbook
from apps.startups.models import Laureate

from . import serializers as s
from .admin_views import IsPanelAdmin
from .office_views import LIST_LIMIT, MAX_UPLOAD_MB


@api_view(['GET'])
@permission_classes([AllowAny])
def laureates(request):
    """Ochiq ro'yxat: `?yil=2025&q=robot`. Yangi yil birinchi."""
    published = Laureate.objects.filter(is_published=True)
    queryset = published

    year = request.query_params.get('yil')
    if year and year.isdigit():
        queryset = queryset.filter(year=int(year))
    search = (request.query_params.get('q') or '').strip()
    if search:
        queryset = queryset.filter(Q(full_name__icontains=search)
                                   | Q(project_name__icontains=search))

    years = (published.order_by().values('year').annotate(count=Count('id'))
             .order_by('-year'))
    return Response({
        'count': queryset.count(),
        'total': published.count(),
        'national': published.filter(is_national_winner=True).count(),
        'years': [{'value': row['year'], 'count': row['count']} for row in years],
        'results': s.LaureateSerializer(queryset.order_by('-year', 'id')[:LIST_LIMIT], many=True,
                                        context={'request': request}).data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def laureate_detail(request, pk):
    item = get_object_or_404(Laureate, pk=pk, is_published=True)
    data = s.LaureateSerializer(item, context={'request': request}).data
    # Pastda «Shu yilgi boshqa g'oliblar»
    related = (Laureate.objects.filter(is_published=True, year=item.year)
               .exclude(pk=item.pk).order_by('?')[:4])
    data['related'] = s.LaureateSerializer(related, many=True, context={'request': request}).data
    return Response(data)


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

class PanelLaureates(APIView):
    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        queryset = Laureate.objects.all().order_by('-year', 'id')
        search = (request.query_params.get('q') or '').strip()
        if search:
            queryset = queryset.filter(Q(full_name__icontains=search)
                                       | Q(project_name__icontains=search))
        return Response({
            'count': queryset.count(),
            'results': s.PanelLaureateSerializer(queryset[:LIST_LIMIT], many=True,
                                                 context={'request': request}).data,
        })

    def post(self, request):
        serializer = s.PanelLaureateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PanelLaureateDetail(APIView):
    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def patch(self, request, pk):
        item = get_object_or_404(Laureate, pk=pk)
        serializer = s.PanelLaureateSerializer(item, data=request.data, partial=True,
                                               context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PanelLaureateImport(APIView):
    """Excel (.xlsx): faqat kerakli ustunlar va ichidagi rasmlar olinadi."""

    permission_classes = [IsPanelAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': "Excel faylni tanlang."}, status=status.HTTP_400_BAD_REQUEST)
        if not upload.name.lower().endswith(('.xlsx', '.xlsm')):
            return Response({'detail': "Faqat .xlsx formatidagi Excel fayl qabul qilinadi."},
                            status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_UPLOAD_MB * 1024 * 1024:
            return Response({'detail': f"Fayl {MAX_UPLOAD_MB} MB dan oshmasin."},
                            status=status.HTTP_400_BAD_REQUEST)

        result = import_workbook(upload)
        if 'detail' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
