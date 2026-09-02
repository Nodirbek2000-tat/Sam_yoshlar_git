from django.db import models

from apps.core.constants import Status
from apps.core.models import TimeStampedModel


class AppealCategory(models.TextChoices):
    FINANCE = 'moliya', "Moliyaviy qo'llab-quvvatlash"
    LEGAL = 'huquqiy', "Huquqiy yordam"
    EDUCATION = 'talim', "Ta'lim va trening"
    EXPORT = 'eksport', "Eksport masalalari"
    TAX = 'soliq', "Soliq masalalari"
    PARTNERSHIP = 'hamkorlik', "Hamkorlik"
    OTHER = 'boshqa', "Boshqa"


class Appeal(TimeStampedModel):
    """Kabinetdagi 'Murojaatlar' — foydalanuvchidan kengashga."""

    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi", on_delete=models.CASCADE,
                             related_name='appeals')
    subject = models.CharField("Mavzu", max_length=200)
    category = models.CharField("Kategoriya", max_length=20, choices=AppealCategory.choices,
                                default=AppealCategory.OTHER)
    message = models.TextField("Murojaat matni")
    attachment = models.FileField("Fayl", upload_to='appeals/%Y/%m/', blank=True)

    status = models.CharField("Holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    response = models.TextField("Javob", blank=True)
    responded_at = models.DateTimeField("Javob berilgan vaqt", null=True, blank=True)
    responded_by = models.ForeignKey('accounts.User', verbose_name="Javob bergan",
                                     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='answered_appeals')

    class Meta:
        verbose_name = "Murojaat"
        verbose_name_plural = "Murojaatlar"
        ordering = ['-created_at']

    def __str__(self):
        return self.subject


class Suggestion(TimeStampedModel):
    """Kabinetdagi 'Takliflar' — platformani yaxshilash bo'yicha takliflar."""

    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi", on_delete=models.CASCADE,
                             related_name='suggestions')
    title = models.CharField("Taklif nomi", max_length=200)
    description = models.TextField("Tavsif")
    expected_benefit = models.TextField("Kutilayotgan foyda", blank=True)

    status = models.CharField("Holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    response = models.TextField("Javob", blank=True)
    votes = models.PositiveIntegerField("Ovozlar", default=0)

    class Meta:
        verbose_name = "Taklif"
        verbose_name_plural = "Takliflar"
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class NotificationType(models.TextChoices):
    INFO = 'info', "Ma'lumot"
    SUCCESS = 'success', "Muvaffaqiyat"
    WARNING = 'warning', "Ogohlantirish"
    EVENT = 'event', "Tadbir"


class Notification(TimeStampedModel):
    """Kabinetdagi 'Bildirishnomalar'."""

    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi", on_delete=models.CASCADE,
                             related_name='notifications')
    title = models.CharField("Sarlavha", max_length=200)
    message = models.TextField("Matn", blank=True)
    type = models.CharField("Turi", max_length=20, choices=NotificationType.choices,
                            default=NotificationType.INFO)
    link = models.CharField("Havola", max_length=300, blank=True)
    is_read = models.BooleanField("O'qilgan", default=False)

    class Meta:
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def icon(self):
        return {
            NotificationType.INFO: 'ℹ️',
            NotificationType.SUCCESS: '✅',
            NotificationType.WARNING: '⚠️',
            NotificationType.EVENT: '📅',
        }.get(self.type, 'ℹ️')
