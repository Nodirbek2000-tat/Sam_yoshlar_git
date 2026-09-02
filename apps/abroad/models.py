from django.db import models
from django.urls import reverse

from apps.core.constants import Region, Status
from apps.core.models import TimeStampedModel

from .countries import COUNTRY_CHOICES, color_of, short_of


class PeerPurpose(models.TextChoices):
    STUDY = 'study', "O'qiyapman"
    WORK = 'work', "Ishlayapman"
    BUSINESS = 'business', "Biznes yuritaman"
    RESEARCH = 'research', "Ilmiy tadqiqot"
    INTERNSHIP = 'internship', "Amaliyot / stajirovka"
    OTHER = 'other', "Boshqa"


PURPOSE_ICONS = {
    PeerPurpose.STUDY: '🎓',
    PeerPurpose.WORK: '💼',
    PeerPurpose.BUSINESS: '🚀',
    PeerPurpose.RESEARCH: '🔬',
    PeerPurpose.INTERNSHIP: '📋',
    PeerPurpose.OTHER: '✨',
}


class Peer(TimeStampedModel):
    """Chet elda o'qiyotgan yoki ishlayotgan yurtdoshimiz.

    Maqsad — vatandagi yoshlar ular bilan bog'lanib, tajriba almashsin.
    """

    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi",
                             on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='peer_profiles')

    full_name = models.CharField("F.I.O.", max_length=150)
    photo = models.ImageField("Rasm", upload_to='peers/%Y/%m/', blank=True)

    country = models.CharField("Davlat", max_length=20, choices=COUNTRY_CHOICES, db_index=True)
    city = models.CharField("Shahar", max_length=100, blank=True)
    home_region = models.CharField("O'zbekistondagi hududi", max_length=30,
                                   choices=Region.choices, blank=True)

    purpose = models.CharField("U yerda nima qilyapti", max_length=20,
                               choices=PeerPurpose.choices, default=PeerPurpose.STUDY)
    institution = models.CharField("Universitet / kompaniya", max_length=200, blank=True)
    field = models.CharField("Yo'nalish / kasb", max_length=150, blank=True)
    since_year = models.PositiveIntegerField("Qaysi yildan beri", null=True, blank=True)

    about = models.TextField("O'zi haqida")
    can_help = models.TextField("Nimada yordam bera oladi", blank=True)

    telegram = models.CharField("Telegram", max_length=100, blank=True)
    instagram = models.CharField("Instagram", max_length=100, blank=True)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Telefon", max_length=25, blank=True)

    status = models.CharField("Holat", max_length=20, choices=Status.choices,
                              default=Status.PENDING)
    is_published = models.BooleanField("Ko'rinsin", default=True)
    admin_note = models.TextField("Admin izohi", blank=True)

    class Meta:
        verbose_name = "Chet eldagi tengdosh"
        verbose_name_plural = "Chet eldagi tengdoshlar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} — {self.get_country_display()}"

    def get_absolute_url(self):
        return reverse('abroad:detail', kwargs={'pk': self.pk})

    @property
    def flag(self):
        """Davlat kodi — bayroq emoji o'rniga (Windows'da bir xil ko'rinadi)."""
        return short_of(self.country)

    @property
    def country_color(self):
        return color_of(self.country)

    @property
    def purpose_icon(self):
        return PURPOSE_ICONS.get(self.purpose, '✨')

    @property
    def initials(self):
        parts = self.full_name.split()
        return ''.join(p[0].upper() for p in parts[:2]) or '?'

    @property
    def has_contacts(self):
        return any([self.telegram, self.instagram, self.email, self.phone])
