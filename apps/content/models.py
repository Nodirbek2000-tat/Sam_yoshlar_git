from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.constants import Region, SamarqandDistrict
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
    AnnouncementType.GRANT: 'ic-money',
    AnnouncementType.CREDIT: 'ic-building',
    AnnouncementType.CONTEST: 'ic-trophy',
    AnnouncementType.SEMINAR: 'ic-books',
    AnnouncementType.TRAINING: 'ic-graduation',
    AnnouncementType.VACANCY: 'ic-briefcase',
    AnnouncementType.STATE_PROGRAM: 'ic-bank',
}


#: Yangilik videosi: brauzerda to'g'ridan-to'g'ri o'ynaydigan formatlar
NEWS_VIDEO_EXTENSIONS = ['mp4', 'webm', 'mov', 'm4v']
NEWS_VIDEO_MAX_MB = 25
NEWS_PHOTO_LIMIT = 20


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
    video = models.FileField("Video", upload_to='news/videos/%Y/%m/', blank=True,
                             validators=[FileExtensionValidator(NEWS_VIDEO_EXTENSIONS)])
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
        indexes = [models.Index(fields=['is_published', '-published_at'])]

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


class NewsPhoto(TimeStampedModel):
    """Yangilikning qo'shimcha rasmlari (galereya). Asosiy rasm — `News.image`."""

    news = models.ForeignKey(News, verbose_name="Yangilik", on_delete=models.CASCADE,
                             related_name='photos')
    image = models.ImageField("Rasm", upload_to='news/gallery/%Y/%m/')
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Yangilik rasmi"
        verbose_name_plural = "Yangilik rasmlari"
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.news} — rasm #{self.pk}"


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
        indexes = [models.Index(fields=['is_published', 'starts_at'])]

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
    # Kartada ikonka o'rniga shu rasm chiqadi
    image = models.ImageField("Rasm", upload_to='announcements/images/%Y/%m/', blank=True)
    file = models.FileField("Fayl", upload_to='announcements/%Y/%m/', blank=True)
    # «Murojaat qilish» tugmasi shu yerga olib boradi: tashkilot sayti,
    # ariza shakli yoki boshqa havola
    apply_url = models.URLField("Murojaat havolasi", max_length=500, blank=True)
    posted_at = models.DateField("Joylangan sana", default=timezone.localdate)
    deadline = models.DateField("Muddat", null=True, blank=True)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "E'lon"
        verbose_name_plural = "E'lonlar"
        ordering = ['-posted_at']
        indexes = [models.Index(fields=['is_active', '-posted_at'])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Announcement, self.title, self.pk, 'elon')
        super().save(*args, **kwargs)

    @property
    def icon(self):
        return ANNOUNCEMENT_ICONS.get(self.type, 'ic-megaphone')

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


# --------------------------------------------------------------------------
# So'rovnomalar — masalan, «Viloyatning eng yaxshi mahalla yetakchisi»
# --------------------------------------------------------------------------

class Poll(TimeStampedModel):
    """Ochiq ovoz berish: bir nechta nomzod, har kim bir marta ovoz beradi.

    Ovozlar soni alohida hisoblagichda saqlanmaydi — har safar `PollVote`
    yozuvlaridan sanaladi. Shunda bir vaqtda kelgan ovozlar yoki nomzod
    o'chirilganda son hech qachon «adashmaydi».
    """

    title = models.CharField("Sarlavha", max_length=250)
    slug = models.SlugField("Havola", max_length=270, unique=True, blank=True)
    description = models.TextField("Tavsif", blank=True)
    image = models.ImageField("Muqova", upload_to='polls/%Y/%m/', blank=True)
    ends_at = models.DateTimeField("Ovoz berish tugashi", null=True, blank=True)
    is_active = models.BooleanField("Saytda ko'rinadi", default=True)
    show_results = models.BooleanField("Natijalar ochiq", default=True,
                                       help_text="O'chiq bo'lsa ovozlar soni faqat panelda ko'rinadi")
    # Kam ovoz bilan «1-o'rin» bo'lib ko'rinib qolmasin: shuncha ovozga yetmagan
    # nomzod ro'yxatda turadi, lekin 1-2-3 o'rin zinapoyasiga chiqmaydi
    podium_min_votes = models.PositiveIntegerField("Peshqadamlik uchun eng kam ovoz", default=1000)

    class Meta:
        verbose_name = "So'rovnoma"
        verbose_name_plural = "So'rovnomalar"
        ordering = ['-created_at']
        indexes = [models.Index(fields=['is_active', '-created_at'])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Poll, self.title, self.pk, 'sorovnoma')
        super().save(*args, **kwargs)

    @property
    def is_closed(self):
        return bool(self.ends_at and self.ends_at <= timezone.now())

    @property
    def is_open(self):
        """Ovoz berish mumkinmi: saytda ko'rinadi va muddati o'tmagan."""
        return self.is_active and not self.is_closed


class PollOption(TimeStampedModel):
    """So'rovnomadagi bitta nomzod — mahalla yetakchisi yoki boshqa variant."""

    poll = models.ForeignKey(Poll, verbose_name="So'rovnoma", on_delete=models.CASCADE,
                             related_name='options')
    name = models.CharField("F.I.O. / nomi", max_length=150)
    mahalla = models.CharField("Mahalla", max_length=150, blank=True)
    district = models.CharField("Tuman / shahar", max_length=30, blank=True,
                                choices=SamarqandDistrict.choices)
    note = models.CharField("Qisqa ma'lumot", max_length=300, blank=True)
    photo = models.ImageField("Rasm", upload_to='polls/options/%Y/%m/', blank=True)
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "Nomzod"
        verbose_name_plural = "Nomzodlar"
        ordering = ['order', 'pk']

    def __str__(self):
        return self.name


class PollVote(TimeStampedModel):
    """Bitta ovoz. Bir kishi bitta so'rovnomada faqat bir marta ovoz beradi —
    buni baza o'zi kafolatlaydi (bir vaqtda ikki marta bosilsa ham)."""

    poll = models.ForeignKey(Poll, verbose_name="So'rovnoma", on_delete=models.CASCADE,
                             related_name='votes')
    option = models.ForeignKey(PollOption, verbose_name="Nomzod", on_delete=models.CASCADE,
                               related_name='votes')
    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi",
                             on_delete=models.CASCADE, related_name='poll_votes')

    class Meta:
        verbose_name = "So'rovnoma ovozi"
        verbose_name_plural = "So'rovnoma ovozlari"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['poll', 'user'], name='uniq_poll_vote_per_user'),
        ]

    def __str__(self):
        return f"{self.user} → {self.option}"
