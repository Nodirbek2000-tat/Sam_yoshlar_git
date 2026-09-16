from django.db import models

from apps.core.constants import Region, Status
from apps.core.models import TimeStampedModel


class BusinessSphere(models.TextChoices):
    IT = 'it', "IT va raqamlashtirish"
    AGRICULTURE = 'qishloq_xojaligi', "Qishloq xo'jaligi"
    MANUFACTURING = 'ishlab_chiqarish', "Ishlab chiqarish"
    SERVICES = 'xizmat', "Xizmat ko'rsatish"
    TRADE = 'savdo', "Savdo va eksport"
    EDUCATION = 'talim', "Ta'lim va innovatsiya"
    TOURISM = 'turizm', "Turizm"
    HEALTHCARE = 'sogliqni_saqlash', "Sog'liqni saqlash"
    CONSTRUCTION = 'qurilish', "Qurilish"
    FOOD = 'oziq_ovqat', "Oziq-ovqat"
    LOGISTICS = 'logistika', "Logistika"
    OTHER = 'boshqa', "Boshqa"


#: Soha -> ikonka kaliti (frontdagi `CategoryTile` shu kalitni taniydi)
BUSINESS_SPHERE_ICONS = {
    BusinessSphere.IT: 'ic-computer',
    BusinessSphere.AGRICULTURE: 'ic-wheat',
    BusinessSphere.MANUFACTURING: 'ic-package',
    BusinessSphere.SERVICES: 'ic-briefcase',
    BusinessSphere.TRADE: 'ic-cart',
    BusinessSphere.EDUCATION: 'ic-graduation',
    BusinessSphere.TOURISM: 'ic-globe',
    BusinessSphere.HEALTHCARE: 'ic-stethoscope',
    BusinessSphere.CONSTRUCTION: 'ic-building',
    BusinessSphere.FOOD: 'ic-seedling',
    BusinessSphere.LOGISTICS: 'ic-truck',
    BusinessSphere.OTHER: 'ic-briefcase',
}


class BusinessProfile(TimeStampedModel):
    """Tadbirkorning biznes profili — kabinetdagi 'Biznes' bo'limi."""

    user = models.OneToOneField('accounts.User', verbose_name="Foydalanuvchi",
                                on_delete=models.CASCADE, related_name='business')
    name = models.CharField("Korxona nomi", max_length=200)
    sphere = models.CharField("Faoliyat sohasi", max_length=30, choices=BusinessSphere.choices)
    stir = models.CharField("STIR (INN)", max_length=20, blank=True)
    founded_year = models.PositiveIntegerField("Tashkil topgan yili", null=True, blank=True)
    employees = models.PositiveIntegerField("Xodimlar soni", default=1)
    region = models.CharField("Viloyat", max_length=30, choices=Region.choices, blank=True)
    district = models.CharField("Tuman / shahar", max_length=100, blank=True)
    address = models.CharField("Manzil", max_length=250, blank=True)
    description = models.TextField("Biznes haqida", blank=True)
    logo = models.ImageField("Logotip", upload_to='business/logos/%Y/%m/', blank=True)
    website = models.URLField("Veb-sayt", blank=True)
    phone = models.CharField("Telefon", max_length=25, blank=True)
    email = models.EmailField("Email", blank=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)
    instagram = models.CharField("Instagram", max_length=100, blank=True)
    status = models.CharField("Holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    is_public = models.BooleanField("Ommaviy ro'yxatda ko'rinsin", default=True)

    class Meta:
        verbose_name = "Biznes profil"
        verbose_name_plural = "Biznes profillar"
        ordering = ['-created_at']
        indexes = [models.Index(fields=['is_public', 'status', '-created_at'])]

    def __str__(self):
        return self.name

    @property
    def sphere_icon(self):
        return BUSINESS_SPHERE_ICONS.get(self.sphere, 'ic-briefcase')


class Product(TimeStampedModel):
    """Kabinetdagi 'Mahsulotlar' bo'limi."""

    business = models.ForeignKey(BusinessProfile, verbose_name="Biznes", on_delete=models.CASCADE,
                                 related_name='products')
    name = models.CharField("Nomi", max_length=200)
    description = models.TextField("Tavsif", blank=True)
    price = models.DecimalField("Narxi (so'm)", max_digits=14, decimal_places=2, null=True, blank=True)
    unit = models.CharField("O'lchov birligi", max_length=40, blank=True, default="dona")
    image = models.ImageField("Rasm", upload_to='business/products/%Y/%m/', blank=True)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class GalleryImage(TimeStampedModel):
    """Kabinetdagi 'Galereya' bo'limi."""

    business = models.ForeignKey(BusinessProfile, verbose_name="Biznes", on_delete=models.CASCADE,
                                 related_name='gallery')
    image = models.ImageField("Rasm", upload_to='business/gallery/%Y/%m/')
    caption = models.CharField("Izoh", max_length=200, blank=True)

    class Meta:
        verbose_name = "Galereya rasmi"
        verbose_name_plural = "Galereya rasmlari"
        ordering = ['-created_at']

    def __str__(self):
        return self.caption or f"Rasm #{self.pk}"


class DocumentType(models.TextChoices):
    CERTIFICATE = 'guvohnoma', "Guvohnoma"
    LICENSE = 'litsenziya', "Litsenziya"
    CONTRACT = 'shartnoma', "Shartnoma"
    REPORT = 'hisobot', "Hisobot"
    OTHER = 'boshqa', "Boshqa"


class Document(TimeStampedModel):
    """Kabinetdagi 'Hujjatlar' bo'limi."""

    business = models.ForeignKey(BusinessProfile, verbose_name="Biznes", on_delete=models.CASCADE,
                                 related_name='documents')
    title = models.CharField("Nomi", max_length=200)
    type = models.CharField("Turi", max_length=20, choices=DocumentType.choices,
                            default=DocumentType.OTHER)
    file = models.FileField("Fayl", upload_to='business/documents/%Y/%m/')
    note = models.CharField("Izoh", max_length=250, blank=True)

    class Meta:
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def size_kb(self):
        try:
            return round(self.file.size / 1024)
        except (ValueError, OSError):
            return 0
