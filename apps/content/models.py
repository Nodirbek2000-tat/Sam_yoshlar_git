from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.constants import Region
from apps.core.models import TimeStampedModel


class NewsCategory(models.TextChoices):
    GRANT = 'grant', "Grant"
    FORUM = 'forum', "Forum"
    TRAINING = 'trening', "Trening"
    CREDIT = 'kredit', "Kredit"
    EXPORT = 'eksport', "Eksport"
    CONTEST = 'tanlov', "Tanlov"


class AnnouncementType(models.TextChoices):
    GRANT = 'grant', "Grant"
    CREDIT = 'kredit', "Kredit"
    CONTEST = 'tanlov', "Tanlov"
    SEMINAR = 'seminar', "Seminar"
    TRAINING = 'trening', "Trening"
    VACANCY = 'vakansiya', "Vakansiya"
    STATE_PROGRAM = 'davlat_dasturi', "Davlat dasturi"


ANNOUNCEMENT_ICONS = {
    AnnouncementType.GRANT: '💰',
    AnnouncementType.CREDIT: '🏦',
    AnnouncementType.CONTEST: '🏆',
    AnnouncementType.SEMINAR: '📚',
    AnnouncementType.TRAINING: '🎓',
    AnnouncementType.VACANCY: '💼',
    AnnouncementType.STATE_PROGRAM: '🏛️',
}


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class News(TimeStampedModel):
    title = models.CharField("Sarlavha", max_length=250)
    slug = models.SlugField("Havola", max_length=270, unique=True, blank=True)
    category = models.CharField("Kategoriya", max_length=20, choices=NewsCategory.choices)
    excerpt = models.TextField("Qisqacha", max_length=500)
    body = models.TextField("Matn")
    image = models.ImageField("Rasm", upload_to='news/%Y/%m/', blank=True)
    author = models.ForeignKey('accounts.User', verbose_name="Muallif", on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='news')
    author_name = models.CharField("Muallif ismi", max_length=150, blank=True)
    published_at = models.DateTimeField("Chop etilgan sana", default=timezone.now)
    is_published = models.BooleanField("Chop etilgan", default=True)
    is_featured = models.BooleanField("Asosiy yangilik", default=False)
    views = models.PositiveIntegerField("Ko'rishlar", default=0)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        verbose_name = "Yangilik"
        verbose_name_plural = "Yangiliklar"
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(News, self.title, self.pk, 'yangilik')
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('content:news_detail', kwargs={'slug': self.slug})

    @property
    def display_author(self):
        return self.author.full_name if self.author else self.author_name


class Event(TimeStampedModel):
    title = models.CharField("Nomi", max_length=250)
    slug = models.SlugField("Havola", max_length=270, unique=True, blank=True)
    description = models.TextField("Tavsif")
    starts_at = models.DateTimeField("Boshlanish vaqti")
    ends_at = models.DateTimeField("Tugash vaqti", null=True, blank=True)
    location = models.CharField("Manzil", max_length=250)
    region = models.CharField("Viloyat", max_length=30, choices=Region.choices, blank=True)
    capacity = models.PositiveIntegerField("Ishtirokchilar limiti", default=100)
    image = models.ImageField("Rasm", upload_to='events/%Y/%m/', blank=True)
    is_published = models.BooleanField("Chop etilgan", default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        verbose_name = "Tadbir"
        verbose_name_plural = "Tadbirlar"
        ordering = ['starts_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Event, self.title, self.pk, 'tadbir')
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('content:event_detail', kwargs={'slug': self.slug})

    @property
    def is_past(self):
        return self.starts_at < timezone.now()

    @property
    def registered_count(self):
        return self.registrations.filter(is_cancelled=False).count()

    @property
    def seats_left(self):
        return max(self.capacity - self.registered_count, 0)

    @property
    def is_full(self):
        return self.seats_left == 0

    @property
    def fill_percent(self):
        if not self.capacity:
            return 0
        return min(round(self.registered_count / self.capacity * 100), 100)

    def is_registered(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.registrations.filter(user=user, is_cancelled=False).exists()


class EventRegistration(TimeStampedModel):
    event = models.ForeignKey(Event, verbose_name="Tadbir", on_delete=models.CASCADE,
                              related_name='registrations')
    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi", on_delete=models.CASCADE,
                             related_name='event_registrations')
    note = models.TextField("Izoh", blank=True)
    is_cancelled = models.BooleanField("Bekor qilingan", default=False)
    attended = models.BooleanField("Qatnashgan", default=False)

    class Meta:
        verbose_name = "Tadbirga yozilish"
        verbose_name_plural = "Tadbirga yozilishlar"
        unique_together = [('event', 'user')]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} — {self.event.title}"


class Announcement(TimeStampedModel):
    title = models.CharField("Sarlavha", max_length=250)
    slug = models.SlugField("Havola", max_length=270, unique=True, blank=True)
    type = models.CharField("Turi", max_length=20, choices=AnnouncementType.choices)
    body = models.TextField("Matn")
    file = models.FileField("Fayl", upload_to='announcements/%Y/%m/', blank=True)
    posted_at = models.DateField("Joylangan sana", default=timezone.localdate)
    deadline = models.DateField("Muddat", null=True, blank=True)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "E'lon"
        verbose_name_plural = "E'lonlar"
        ordering = ['-posted_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Announcement, self.title, self.pk, 'elon')
        super().save(*args, **kwargs)

    @property
    def icon(self):
        return ANNOUNCEMENT_ICONS.get(self.type, '📢')

    @property
    def is_expired(self):
        return bool(self.deadline and self.deadline < timezone.localdate())

    @property
    def status_label(self):
        if self.is_expired:
            return "Muddati tugagan"
        return "Faol" if self.is_active else "Yopilgan"


def _unique_slug(model, title, pk, fallback):
    """Sarlavhadan takrorlanmaydigan slug yasaydi."""
    base = slugify(title, allow_unicode=False)[:200] or fallback
    slug, counter = base, 2
    while model.objects.filter(slug=slug).exclude(pk=pk).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug
