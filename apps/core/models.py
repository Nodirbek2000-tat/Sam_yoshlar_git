from django.db import models
from django.utils import timezone

from .constants import Region


class TimeStampedModel(models.Model):
    """Barcha modellar uchun yaratilgan/yangilangan vaqt."""

    created_at = models.DateTimeField("Yaratilgan", default=timezone.now, editable=False)
    updated_at = models.DateTimeField("Yangilangan", auto_now=True)

    class Meta:
        abstract = True


class SiteSetting(TimeStampedModel):
    """Footer va header uchun bitta sozlamalar yozuvi (singleton)."""

    site_name = models.CharField("Sayt nomi", max_length=120, default="sam-yosh tadbirkor.uz")
    tagline = models.TextField(
        "Qisqa tavsif",
        default="O'zbekiston yosh tadbirkorlarini birlashtiruvchi, qo'llab-quvvatlovchi va "
                "rivojlantirishga xizmat qiluvchi yagona axborot platformasi.",
    )
    address = models.CharField("Manzil", max_length=255, blank=True)
    phone = models.CharField("Telefon", max_length=50, blank=True)
    email = models.EmailField("Email", blank=True)
    work_hours = models.CharField("Ish vaqti", max_length=120, blank=True)
    telegram_url = models.URLField("Telegram", blank=True)
    instagram_url = models.URLField("Instagram", blank=True)
    facebook_url = models.URLField("Facebook", blank=True)
    youtube_url = models.URLField("YouTube", blank=True)

    mission = models.TextField(
        "Maqsad",
        default="O'zbekiston yosh tadbirkorlarini qo'llab-quvvatlash, ularning salohiyatini "
                "oshirish va biznes muhitini yaxshilash.",
    )
    vision = models.TextField(
        "Viziya",
        default="Har bir yosh tadbirkor o'z g'oyasini muvaffaqiyatli biznesga aylantira oladigan "
                "muhitni yaratish.",
    )
    charter_file = models.FileField("Nizom fayli", upload_to='documents/', blank=True)

    class Meta:
        verbose_name = "Sayt sozlamasi"
        verbose_name_plural = "Sayt sozlamalari"

    def __str__(self):
        return self.site_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Task(TimeStampedModel):
    """Kengash vazifalari — 'Kengash haqida' sahifasidagi ✅ ro'yxati."""

    text = models.CharField("Vazifa", max_length=300)
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Kengash vazifasi"
        verbose_name_plural = "Kengash vazifalari"
        ordering = ['order', 'pk']

    def __str__(self):
        return self.text


class LeaderRole(models.TextChoices):
    CHAIRMAN = 'chairman', "Kengash Raisi"
    SECRETARY = 'secretary', "Kengash Kotibi"
    MEMBER = 'member', "Kengash A'zosi"


class Leader(TimeStampedModel):
    """Rahbariyat va kengash a'zolari."""

    full_name = models.CharField("F.I.O.", max_length=150)
    position = models.CharField("Lavozim / yo'nalish", max_length=150)
    role = models.CharField("Toifa", max_length=20, choices=LeaderRole.choices,
                            default=LeaderRole.MEMBER)
    bio = models.TextField("Qisqacha ma'lumot", blank=True)
    photo = models.ImageField("Rasm", upload_to='leaders/', blank=True)
    region = models.CharField("Hudud", max_length=30, choices=Region.choices, blank=True)
    order = models.PositiveIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Rahbar / a'zo"
        verbose_name_plural = "Rahbariyat va a'zolar"
        ordering = ['order', 'pk']

    def __str__(self):
        return f"{self.full_name} — {self.position}"

    @property
    def initials(self):
        parts = self.full_name.split()
        return ''.join(p[0].upper() for p in parts[:2])
