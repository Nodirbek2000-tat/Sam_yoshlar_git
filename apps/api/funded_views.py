"""Mablag' olgan startaplar — bosh sahifaning eng tepasidagi bo'lim.

Sayt: ro'yxat (tartib bo'yicha) va jami olingan mablag'. Panel: qo'shish va
tahrirlash; yashirish va o'chirish umumiy `panel_moderate` / `panel_delete` orqali.
"""

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.startups.models import FundedStartup, FundingCurrency

from . import serializers as s
from .admin_views import IsPanelAdmin

#: Bosh sahifadagi lentada shuncha karta
LIST_LIMIT = 60


@api_view(['GET'])
@permission_classes([AllowAny])
def funded_startups(request):
    published = FundedStartup.objects.filter(is_published=True)
    totals = {row['currency']: row['total'] for row in
              published.order_by().values('currency').annotate(total=Sum('amount'))}
    return Response({
        'count': published.count(),
        # Valyutalar alohida qo'shiladi — so'm va dollar aralashmasin
        'totals': {currency: totals.get(currency) or 0 for currency in FundingCurrency.values},
        'results': s.FundedStartupSerializer(published[:LIST_LIMIT], many=True,
                                             context={'request': request}).data,
    })


class PanelFundedStartups(APIView):
    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        queryset = FundedStartup.objects.all()
        return Response({
            'count': queryset.count(),
            'results': s.PanelFundedStartupSerializer(queryset, many=True,
                                                      context={'request': request}).data,
        })

    def post(self, request):
        serializer = s.PanelFundedStartupSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PanelFundedStartupDetail(APIView):
    permission_classes = [IsPanelAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def patch(self, request, pk):
        item = get_object_or_404(FundedStartup, pk=pk)
        serializer = s.PanelFundedStartupSerializer(item, data=request.data, partial=True,
                                                    context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
