from django.db import models

from apps.core.constants import Region, Status
from apps.core.models import TimeStampedModel


class StartupSphere(models.TextChoices):
    IT = 'it', "IT / Dasturiy ta'minot"
    FINTECH = 'fintech', "Fintech"
    EDTECH = 'edtech', "EdTech — ta'lim"
    AGROTECH = 'agrotech', "AgroTech — qishloq xo'jaligi"
    MEDTECH = 'medtech', "MedTech — tibbiyot"
    ECOMMERCE = 'ecommerce', "E-commerce / Savdo"
    LOGISTICS = 'logistics', "Logistika"
    GREEN = 'green', "Ekologiya va yashil energiya"
    MEDIA = 'media', "Media va kontent"
    OTHER = 'other', "Boshqa"


STARTUP_SPHERE_ICONS = {
    StartupSphere.IT: '💻',
    StartupSphere.FINTECH: '💳',
    StartupSphere.EDTECH: '🎓',
    StartupSphere.AGROTECH: '🌾',
    StartupSphere.MEDTECH: '🩺',
    StartupSphere.ECOMMERCE: '🛒',
    StartupSphere.LOGISTICS: '🚚',
    StartupSphere.GREEN: '🌱',
    StartupSphere.MEDIA: '🎬',
    StartupSphere.OTHER: '✨',
}


class StartupStage(models.TextChoices):
    IDEA = 'idea', "G'oya bosqichi"
    MVP = 'mvp', "MVP tayyor"
    LAUNCHED = 'launched', "Bozorga chiqqan"
    SCALING = 'scaling', "Kengaytirilmoqda"


class Startup(TimeStampedModel):
    """/startupperlar sahifasidagi 2 qadamli ariza."""

    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi", on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='startups')

    # 1-qadam — shaxsiy ma'lumotlar
    full_name = models.CharField("F.I.O.", max_length=150)
    phone = models.CharField("Telefon raqami", max_length=25)
    email = models.EmailField("Email")
    birth_date = models.DateField("Tug'ilgan sana", null=True, blank=True)
    region = models.CharField("Viloyat", max_length=30, choices=Region.choices)
    district = models.CharField("Tuman / shahar", max_length=100, blank=True)

    # 2-qadam — startup ma'lumotlari
    name = models.CharField("StartUp nomi", max_length=200)
    sphere = models.CharField("Yo'nalish", max_length=20, choices=StartupSphere.choices)
    stage = models.CharField("Bosqich", max_length=20, choices=StartupStage.choices,
                             default=StartupStage.IDEA)
    about = models.TextField("StartUp haqida")
    problem_solved = models.TextField("Qanday muammoni hal qiladi", blank=True)
    team_size = models.PositiveIntegerField("Jamoa a'zolari soni", default=1)
    needed_investment = models.DecimalField("Kerakli investitsiya (so'm)", max_digits=14,
                                            decimal_places=2, null=True, blank=True)
    pitch_file = models.FileField("Pitch fayl", upload_to='startups/pitch/%Y/%m/', blank=True)
    logo = models.ImageField("Logotip", upload_to='startups/logos/%Y/%m/', blank=True)
    website = models.URLField("Veb-sayt", blank=True)

    status = models.CharField("Holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_note = models.TextField("Admin izohi", blank=True)
    is_public = models.BooleanField("Ommaviy ro'yxatda ko'rinsin", default=True)

    class Meta:
        verbose_name = "StartUp"
        verbose_name_plural = "StartUplar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.full_name}"

    @property
    def sphere_icon(self):
        return STARTUP_SPHERE_ICONS.get(self.sphere, '🚀')
