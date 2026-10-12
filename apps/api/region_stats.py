"""Panel: hududlar statistikasi — tuman va mahallalar kesimida.

Foydalanuvchilar o'z tumani va mahallasi bo'yicha, tashabbuslar yozilgan
paytdagi hudud bo'yicha (eski tashabbuslarda — muallifning hududi),
ovozlar esa ovoz bergan odamning hududi bo'yicha sanaladi.

Mahalla nomi erkin yoziladi, shuning uchun `mahalla_key` bo'yicha
yig'iladi va eng ko'p yozilgan ko'rinishi nom sifatida olinadi.
"""

from collections import Counter, defaultdict

from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.core.constants import SamarqandDistrict
from apps.core.mahalla import mahalla_key
from apps.initiatives.models import Initiative, InitiativeVote

from .admin_views import IsPanelAdmin

User = get_user_model()

#: Tumani ko'rsatilmaganlar uchun qator
UNKNOWN = ''


def _bucket():
    return {'users': 0, 'initiatives': 0, 'votes': 0}


class Tally:
    """Tuman → mahalla → sonlar. Mahalla bo'sh bo'lsa — «ko'rsatilmagan»ga."""

    def __init__(self):
        self.districts = defaultdict(_bucket)
        self.without_mahalla = defaultdict(_bucket)
        self.mahallas = defaultdict(lambda: defaultdict(_bucket))
        self.names = defaultdict(Counter)

    def add(self, district, mahalla, field, amount=1):
        district = district if district in SamarqandDistrict.labels else UNKNOWN
        self.districts[district][field] += amount
        key = mahalla_key(mahalla)
        if not key:
            self.without_mahalla[district][field] += amount
            return
        self.mahallas[district][key][field] += amount
        self.names[(district, key)][mahalla.strip()] += 1

    def mahalla_rows(self, district):
        rows = [{'name': self.names[(district, key)].most_common(1)[0][0], **counts}
                for key, counts in self.mahallas[district].items()]
        rows.sort(key=lambda row: (-row['users'], -row['initiatives'], -row['votes'], row['name']))
        return rows


class PanelRegionStats(APIView):
    permission_classes = [IsPanelAdmin]

    def get(self, request):
        tally = Tally()

        # Panel ro'yxati bilan bir xil: tashkilotlar va bosh adminlar foydalanuvchi emas
        people = (User.objects.exclude(role=Role.ORGANIZATION).filter(is_superuser=False)
                  .values_list('district', 'mahalla'))
        for district, mahalla in people.iterator(chunk_size=2000):
            tally.add(district, mahalla, 'users')

        initiatives = (Initiative.objects.filter(is_published=True)
                       .values_list('district', 'mahalla', 'author__district', 'author__mahalla'))
        for district, mahalla, author_district, author_mahalla in initiatives.iterator(chunk_size=2000):
            if district:
                tally.add(district, mahalla, 'initiatives')
            else:
                tally.add(author_district or '', author_mahalla or '', 'initiatives')

        votes = (InitiativeVote.objects.filter(user__isnull=False)
                 .values_list('user__district', 'user__mahalla'))
        for district, mahalla in votes.iterator(chunk_size=5000):
            tally.add(district or '', mahalla or '', 'votes')

        districts = []
        for value, label in SamarqandDistrict.choices:
            mahallas = tally.mahalla_rows(label)
            districts.append({
                'value': value, 'label': label, **tally.districts[label],
                'mahalla_count': len(mahallas),
                'without_mahalla': tally.without_mahalla[label],
                'mahallas': mahallas,
            })
        districts.sort(key=lambda row: (-row['users'], -row['initiatives'], row['label']))

        totals = _bucket()
        for counts in tally.districts.values():
            for field in totals:
                totals[field] += counts[field]

        return Response({
            'totals': {**totals,
                       'mahallas': sum(row['mahalla_count'] for row in districts),
                       'users_with_mahalla': totals['users'] - sum(
                           counts['users'] for counts in tally.without_mahalla.values())},
            'districts': districts,
            'unknown': tally.districts[UNKNOWN],
        })
