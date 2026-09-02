from django.db import models
from django.utils import timezone

from apps.core.constants import Region, Status
from apps.core.models import TimeStampedModel

from .directions import DEFAULT_DIRECTION, DIRECTION_CHOICES, get_direction


class ProblemCategory(models.TextChoices):
    """Tashkilot anketasining 10 ta savol bloki (frontenddagi 2-11 qadamlar)."""

    BOTTLENECKS = 'bottlenecks', "Jarayonlardagi to'siqlar"
    HUMAN = 'human', "Inson omili"
    COMMUNICATION = 'communication', "Muloqot va axborot oqimi"
    TECHNOLOGY = 'technology', "Texnologiya va avtomatlashtirish"
    CUSTOMERS = 'customers', "Mijozlar fikri"
    FINANCE = 'finance', "Moliya va xarajatlar"
    MANAGEMENT = 'management', "Boshqaruv va nazorat"
    STRATEGY = 'strategy', "Strategiya va ijro xatoligi"
    COMPETITION = 'competition', "Tashqi xavflar va raqobat"
    MAIN = 'main', "Asosiy muammo"


#: Anketadagi har bir qadam: kategoriya, tartib raqami, ikonka va savol matni.
PROBLEM_QUESTIONS = [
    {
        'category': ProblemCategory.BOTTLENECKS, 'number': 1, 'icon': '⛔',
        'question': "Tashkilotingizdagi qaysi amaliy jarayon (yoki ish bosqichi) eng ko'p vaqt "
                    "va resurs talab qiladi? Nima uchun?",
    },
    {
        'category': ProblemCategory.HUMAN, 'number': 2, 'icon': '👥',
        'question': "Xodimlar bilan bog'liq qanday muammolar bor — malaka, motivatsiya, "
                    "kadrlar almashinuvi yoki ish taqsimoti?",
    },
    {
        'category': ProblemCategory.COMMUNICATION, 'number': 3, 'icon': '💬',
        'question': "Bo'limlar o'rtasida axborot qanday uzatiladi? Qayerda ma'lumot yo'qoladi "
                    "yoki kechikadi?",
    },
    {
        'category': ProblemCategory.TECHNOLOGY, 'number': 4, 'icon': '⚙️',
        'question': "Qaysi ishlar hali ham qo'lda bajariladi va avtomatlashtirilishi kerak? "
                    "Mavjud dasturlar yetarlimi?",
    },
    {
        'category': ProblemCategory.CUSTOMERS, 'number': 5, 'icon': '⭐',
        'question': "Mijozlar (yoki fuqarolar) eng ko'p nimadan shikoyat qiladi? "
                    "Ularning fikri qanday yig'iladi?",
    },
    {
        'category': ProblemCategory.FINANCE, 'number': 6, 'icon': '💰',
        'question': "Qaysi xarajatlar asossiz ko'p? Byudjet rejalashtirish qanday amalga oshiriladi?",
    },
    {
        'category': ProblemCategory.MANAGEMENT, 'number': 7, 'icon': '📊',
        'question': "Natijalar qanday o'lchanadi va nazorat qilinadi? Hisobot tizimi qanchalik shaffof?",
    },
    {
        'category': ProblemCategory.STRATEGY, 'number': 8, 'icon': '🎯',
        'question': "Rejalashtirilgan maqsadlarning qaysilari bajarilmay qolmoqda va nima sababdan?",
    },
    {
        'category': ProblemCategory.COMPETITION, 'number': 9, 'icon': '🛡️',
        'question': "Raqobatchilar yoki tashqi omillar (bozor, qonunchilik) qanday xavf tug'dirmoqda?",
    },
    {
        'category': ProblemCategory.MAIN, 'number': 10, 'icon': '🔥',
        'question': "Agar bitta muammoni bugun hal qilish imkoni bo'lsa — bu qaysi muammo bo'lardi?",
    },
]

PROBLEM_QUESTION_MAP = {item['category']: item for item in PROBLEM_QUESTIONS}


class OrganizationSphere(models.TextChoices):
    GOVERNMENT = 'davlat', "Davlat boshqaruvi"
    AGRICULTURE = 'qishloq_xojaligi', "Qishloq xo'jaligi"
    HEALTHCARE = 'tibbiyot', "Tibbiyot"
    EDUCATION = 'talim', "Ta'lim"
    LOGISTICS = 'logistika', "Logistika"
    MANUFACTURING = 'ishlab_chiqarish', "Ishlab chiqarish"
    TRADE = 'savdo', "Savdo"
    SERVICES = 'xizmat', "Xizmat ko'rsatish"
    IT = 'it', "IT"
    OTHER = 'boshqa', "Boshqa"


class Organization(TimeStampedModel):
    """/tashabbuslar/tashkilotlar anketasining 1-qadami."""

    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi", on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='organizations')
    name = models.CharField("Tashkilot nomi", max_length=200)
    sphere = models.CharField("Faoliyat sohasi", max_length=30, choices=OrganizationSphere.choices)
    contact_person = models.CharField("Aloqa shaxsi (F.I.O)", max_length=150)
    phone = models.CharField("Telefon raqami", max_length=25)
    email = models.EmailField("Email", blank=True)
    region = models.CharField("Viloyat", max_length=30, choices=Region.choices, blank=True)
    employees = models.PositiveIntegerField("Xodimlar soni", null=True, blank=True)

    class Meta:
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Problem(TimeStampedModel):
    """Tashkilot kiritgan bitta muammo (anketaning bitta savoliga javob)."""

    organization = models.ForeignKey(Organization, verbose_name="Tashkilot", on_delete=models.CASCADE,
                                     related_name='problems')
    category = models.CharField("Kategoriya", max_length=20, choices=ProblemCategory.choices)
    description = models.TextField("Muammo tavsifi")
    status = models.CharField("Holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    is_published = models.BooleanField("Yoshlarga ko'rinsin", default=True)

    class Meta:
        verbose_name = "Muammo"
        verbose_name_plural = "Muammolar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.organization.name} — {self.get_category_display()}"

    @property
    def icon(self):
        item = PROBLEM_QUESTION_MAP.get(self.category)
        return item['icon'] if item else '❓'

    @property
    def question(self):
        item = PROBLEM_QUESTION_MAP.get(self.category)
        return item['question'] if item else ''

    @property
    def solutions_count(self):
        return self.solutions.count()

    @property
    def age_label(self):
        """Frontenddagi '2 kun oldin' ko'rinishi."""
        delta = timezone.now() - self.created_at
        if delta.days >= 7:
            weeks = delta.days // 7
            return f"{weeks} hafta oldin"
        if delta.days >= 1:
            return f"{delta.days} kun oldin"
        hours = delta.seconds // 3600
        if hours >= 1:
            return f"{hours} soat oldin"
        return "Hozirgina"


class Solution(TimeStampedModel):
    """/tashabbuslar/yoshlar — yosh taklif qilgan yechim."""

    problem = models.ForeignKey(Problem, verbose_name="Muammo", on_delete=models.CASCADE,
                                related_name='solutions')
    author = models.ForeignKey('accounts.User', verbose_name="Muallif", on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='solutions')
    author_name = models.CharField("F.I.O.", max_length=150)
    author_phone = models.CharField("Telefon", max_length=25, blank=True)
    author_email = models.EmailField("Email", blank=True)

    title = models.CharField("Yechim nomi", max_length=200)
    description = models.TextField("Yechim tavsifi")
    technologies = models.CharField("Texnologiyalar va vositalar", max_length=300, blank=True)
    expected_result = models.TextField("Kutilayotgan natija", blank=True)
    attachment = models.FileField("Qo'shimcha fayl", upload_to='solutions/%Y/%m/', blank=True)

    status = models.CharField("Holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_note = models.TextField("Admin izohi", blank=True)

    class Meta:
        verbose_name = "Yechim"
        verbose_name_plural = "Yechimlar"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# --------------------------------------------------------------------------
# Yoshlar Ovozi — tashabbuslar va ovoz berish
# --------------------------------------------------------------------------

class InitiativeKind(models.TextChoices):
    PROBLEM = 'problem', "Muammo"
    IDEA = 'idea', "G'oya"
    PROPOSAL = 'proposal', "Taklif"
    STARTUP = 'startup', "StartUp g'oyasi"


INITIATIVE_KIND_ICONS = {
    InitiativeKind.PROBLEM: '❗',
    InitiativeKind.IDEA: '💡',
    InitiativeKind.PROPOSAL: '📌',
    InitiativeKind.STARTUP: '🚀',
}


class Initiative(TimeStampedModel):
    """Yosh bildirgan tashabbus — muammo, g'oya, taklif yoki startap fikri.

    Har bir tashabbus 14 yo'nalishdan biriga tegishli va ovoz to'playdi.
    """

    direction = models.CharField("Yo'nalish", max_length=20, choices=DIRECTION_CHOICES,
                                 default=DEFAULT_DIRECTION, db_index=True)
    kind = models.CharField("Turi", max_length=20, choices=InitiativeKind.choices,
                            default=InitiativeKind.IDEA)

    title = models.CharField("Sarlavha", max_length=200)
    summary = models.CharField("Qisqa mazmun", max_length=300, blank=True)
    description = models.TextField("Batafsil tavsif")
    expected_result = models.TextField("Kutilayotgan natija", blank=True)

    author = models.ForeignKey('accounts.User', verbose_name="Muallif", on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='initiatives')
    author_name = models.CharField("F.I.O.", max_length=150)
    author_phone = models.CharField("Telefon", max_length=25, blank=True)
    author_email = models.EmailField("Email", blank=True)
    region = models.CharField("Viloyat", max_length=30, choices=Region.choices, blank=True)

    vote_count = models.PositiveIntegerField("Ovozlar", default=0, db_index=True)
    status = models.CharField("Holat", max_length=20, choices=Status.choices,
                              default=Status.APPROVED)
    is_published = models.BooleanField("Ko'rinsin", default=True)
    admin_note = models.TextField("Admin izohi", blank=True)

    class Meta:
        verbose_name = "Tashabbus"
        verbose_name_plural = "Tashabbuslar"
        ordering = ['-vote_count', '-created_at']
        indexes = [models.Index(fields=['direction', '-vote_count'])]

    def __str__(self):
        return self.title

    @property
    def kind_icon(self):
        return INITIATIVE_KIND_ICONS.get(self.kind, '💡')

    @property
    def direction_data(self):
        return get_direction(self.direction)

    @property
    def author_label(self):
        return self.author.full_name if self.author else self.author_name

    @property
    def comment_count(self):
        return self.comments.filter(is_published=True).count()

    @property
    def rank(self):
        """Shu yo'nalish ichidagi o'rni (1 — eng ko'p ovoz)."""
        return Initiative.objects.filter(
            direction=self.direction, is_published=True,
            vote_count__gt=self.vote_count,
        ).count() + 1

    def has_voted(self, user, session_key=None):
        """Shu foydalanuvchi (yoki mehmon sessiyasi) allaqachon ovoz berganmi?"""
        votes = self.votes.all()
        if user is not None and user.is_authenticated:
            return votes.filter(user=user).exists()
        if session_key:
            return votes.filter(user__isnull=True, session_key=session_key).exists()
        return False


class InitiativeVote(TimeStampedModel):
    """Bitta ovoz. Ro'yxatdan o'tgan foydalanuvchi — user bo'yicha,
    mehmon — sessiya kaliti bo'yicha bir marta ovoz bera oladi."""

    initiative = models.ForeignKey(Initiative, verbose_name="Tashabbus", on_delete=models.CASCADE,
                                   related_name='votes')
    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi",
                             on_delete=models.CASCADE, null=True, blank=True,
                             related_name='initiative_votes')
    session_key = models.CharField("Sessiya kaliti", max_length=40, blank=True, db_index=True)

    class Meta:
        verbose_name = "Ovoz"
        verbose_name_plural = "Ovozlar"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['initiative', 'user'],
                                    condition=models.Q(user__isnull=False),
                                    name='uniq_vote_per_user'),
            models.UniqueConstraint(fields=['initiative', 'session_key'],
                                    condition=models.Q(user__isnull=True),
                                    name='uniq_vote_per_session'),
        ]

    def __str__(self):
        return f"{self.initiative.title} ← {self.user or 'mehmon'}"


class InitiativeComment(TimeStampedModel):
    """Tashabbusga bildirilgan taklif — izoh ko'rinishida."""

    initiative = models.ForeignKey(Initiative, verbose_name="Tashabbus", on_delete=models.CASCADE,
                                   related_name='comments')
    author = models.ForeignKey('accounts.User', verbose_name="Muallif", on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='initiative_comments')
    author_name = models.CharField("F.I.O.", max_length=150)
    text = models.TextField("Taklif matni")
    is_published = models.BooleanField("Ko'rinsin", default=True)

    class Meta:
        verbose_name = "Taklif (izoh)"
        verbose_name_plural = "Takliflar (izohlar)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author_name}: {self.text[:40]}"

    @property
    def author_label(self):
        return self.author.full_name if self.author else self.author_name

    @property
    def initials(self):
        parts = self.author_label.split()
        return ''.join(p[0].upper() for p in parts[:2]) or '?'
