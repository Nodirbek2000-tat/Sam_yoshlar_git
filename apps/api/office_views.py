"""Samarqand startuplar ofisi — viloyat reestridagi startaplar.

Sayt: ro'yxat (soha, bosqich, tuman bo'yicha saralash) va har birining sahifasi,
«Bog'lanish» — Telegram orqali. Panel: Excel'dan yuklash, tahrirlash,
yashirish va o'chirish (oxirgi ikkisi umumiy `panel_moderate` / `panel_delete`).
"""

from collections import Counter

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.constants import district_label
from apps.startups.models import OfficeStage, OfficeSphere, OfficeStartup
from apps.startups.office_import import import_workbook

from . import serializers as s
from .admin_views import IsPanelAdmin

#: Ro'yxat bitta javobda keladi (reestr bir necha yuz yozuvdan oshmaydi)
LIST_LIMIT = 1000

#: Yuklanadigan Excel hajmi chegarasi (rasmlar bilan)
MAX_UPLOAD_MB = 20


def _facets(queryset):
    """Saralash tugmalari uchun: har bir soha, bosqich va tumanda nechta loyiha."""
    rows = list(queryset.values_list('sphere', 'stage', 'district'))
    spheres = Counter(row[0] for row in rows)
    stages = Counter(row[1] for row in rows)
    districts = Counter(row[2] for row in rows if row[2])
    return {
        'spheres': [{'value': value, 'label': label, 'count': spheres[value]}
                    for value, label in OfficeSphere.choices if spheres[value]],
        'stages': [{'value': value, 'label': label, 'count': stages[value]}
                   for value, label in OfficeStage.choices if stages[value]],
        'districts': sorted(
            ({'value': value, 'label': district_label(value) or value, 'count': count}
             for value, count in districts.items()),
            key=lambda item: -item['count'],
        ),
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def office_startups(request):
    """Ochiq ro'yxat. `?soha=edtech&bosqich=mvp&hudud=urgut&q=ai`."""
    published = OfficeStartup.objects.filter(is_published=True)
    queryset = published

    sphere = request.query_params.get('soha')
    if sphere in OfficeSphere.values:
        queryset = queryset.filter(sphere=sphere)
    stage = request.query_params.get('bosqich')
    if stage in OfficeStage.values:
        queryset = queryset.filter(stage=stage)
    district = request.query_params.get('hudud')
    if district:
        queryset = queryset.filter(district=district)
    search = (request.query_params.get('q') or '').strip()
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(full_name__icontains=search)
                                   | Q(about__icontains=search))

    # Reestrdagi tartibda (Excel'dagi 1-raqamdan), keyin qo'lda qo'shilganlar
    queryset = queryset.order_by('id')
    return Response({
        'count': queryset.count(),
        'total': published.count(),
        'facets': _facets(published),
        'results': s.OfficeStartupSerializer(queryset[:LIST_LIMIT], many=True,
                                             context={'request': request}).data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def office_startup_detail(request, pk):
    item = get_object_or_404(OfficeStartup, pk=pk, is_published=True)
    data = s.OfficeStartupSerializer(item, context={'request': request}).data

    # Pastda «Shu sohadagi boshqa loyihalar»
    related = (OfficeStartup.objects.filter(is_published=True, sphere=item.sphere)
               .exclude(pk=item.pk).order_by('?')[:4])
    data['related'] = s.OfficeStartupSerializer(related, many=True,
                                                context={'request': request}).data
    return Response(data)


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

class PanelOfficeStartups(APIView):
    """Panel ro'yxati (qidiruv bilan) va qo'lda yangi loyiha qo'shish."""

    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        queryset = OfficeStartup.objects.all().order_by('-created_at', '-id')
        search = (request.query_params.get('q') or '').strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(full_name__icontains=search))
        return Response({
            'count': queryset.count(),
            'results': s.PanelOfficeStartupSerializer(queryset[:LIST_LIMIT], many=True,
                                                      context={'request': request}).data,
        })

    def post(self, request):
        serializer = s.PanelOfficeStartupSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PanelOfficeStartupDetail(APIView):
    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def patch(self, request, pk):
        item = get_object_or_404(OfficeStartup, pk=pk)
        serializer = s.PanelOfficeStartupSerializer(item, data=request.data, partial=True,
                                                    context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PanelOfficeImport(APIView):
    """Excel (.xlsx) reestrni yuklash: faqat kerakli ustunlar va ichidagi rasmlar olinadi."""

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
