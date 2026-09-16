from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from datetime import timedelta

from django.utils import timezone

from apps.core.constants import Region


class Role(models.TextChoices):
    YOUTH = 'yosh', "Yosh"
    ENTREPRENEUR = 'entrepreneur', "Tadbirkor"
    STARTUPPER = 'startupper', "Startupper"
    ORGANIZATION = 'organization', "Tashkilot"
    ADMIN = 'admin', "Administrator"


#: Saytga faqat shu yoshgacha bo'lganlar kiradi (30 yosh ham mumkin)
AGE_LIMIT = 30


class StudyLocation(models.TextChoices):
    UZBEKISTAN = 'uz', "O'zbekistonda"
    ABROAD = 'abroad', "Chet elda"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email majburiy")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', Role.ADMIN)
        extra.setdefault('is_verified', True)
        if extra.get('is_staff') is not True:
            raise ValueError("Superuser is_staff=True bo'lishi kerak")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Email orqali kiradigan foydalanuvchi. Frontenddagi ro'yxatdan o'tish 3 qadamiga mos."""

    email = models.EmailField("Email", unique=True)
    telegram_id = models.BigIntegerField("Telegram ID", unique=True, null=True, blank=True,
                                         db_index=True)
    telegram_username = models.CharField("Telegram username", max_length=64, blank=True)
    full_name = models.CharField("F.I.O.", max_length=150)
    phone = models.CharField("Telefon", max_length=25, blank=True)
    role = models.CharField("Rol", max_length=20, choices=Role.choices, default=Role.ENTREPRENEUR)

    region = models.CharField("Viloyat", max_length=30, choices=Region.choices, blank=True)
    district = models.CharField("Tuman / shahar", max_length=100, blank=True)
    birth_date = models.DateField("Tug'ilgan sana", null=True, blank=True)
    # Botda so'raladi — AGE_LIMIT dan kattalarga kirish kodi berilmaydi
    age = models.PositiveSmallIntegerField("Yoshi", null=True, blank=True)
    study_location = models.CharField("Qayerda ta'lim oladi", max_length=10,
                                      choices=StudyLocation.choices, blank=True)
    avatar = models.ImageField("Rasm", upload_to='avatars/%Y/%m/', blank=True)
    bio = models.TextField("O'zi haqida", blank=True)

    is_active = models.BooleanField("Faol", default=True)
    is_staff = models.BooleanField("Xodim", default=False)
    is_verified = models.BooleanField("Tasdiqlangan", default=False)
    date_joined = models.DateTimeField("Ro'yxatdan o'tgan", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else self.email

    @property
    def initials(self):
        parts = self.full_name.split()
        return ''.join(p[0].upper() for p in parts[:2]) or self.email[0].upper()

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN or self.is_superuser


class RequiredChannel(models.Model):
    """Majburiy obuna kanali yoki guruhi.

    Bot kod berishdan oldin odam shu kanallarga obuna bo'lganini tekshiradi.
    Kanal qo'shilishidan oldin bot o'sha yerda admin bo'lishi shart —
    aks holda a'zolikni tekshira olmaydi.
    """

    chat_id = models.BigIntegerField("Chat ID", unique=True)
    username = models.CharField("Username (@ siz)", max_length=64, blank=True)
    title = models.CharField("Nomi", max_length=200)
    invite_link = models.CharField("Havola", max_length=300, blank=True)
    is_active = models.BooleanField("Majburiy", default=True)
    added_by = models.BigIntegerField("Qo'shgan admin", null=True, blank=True)
    created_at = models.DateTimeField("Qo'shilgan", default=timezone.now)

    class Meta:
        verbose_name = "Majburiy kanal"
        verbose_name_plural = "Majburiy kanallar"
        ordering = ['created_at']

    def __str__(self):
        return self.title

    @property
    def link(self):
        if self.invite_link:
            return self.invite_link
        return f"https://t.me/{self.username}" if self.username else ''

    @property
    def joined_count(self):
        """Bot orqali shu kanalga qo'shilgan odamlar soni."""
        return self.joins.count()


class ChannelJoin(models.Model):
    """Kim qaysi kanalga bot talabi bilan qo'shilgani — statistika uchun."""

    channel = models.ForeignKey(RequiredChannel, verbose_name="Kanal",
                                on_delete=models.CASCADE, related_name='joins')
    telegram_id = models.BigIntegerField("Telegram ID", db_index=True)
    created_at = models.DateTimeField("Qo'shilgan", default=timezone.now)

    class Meta:
        verbose_name = "Kanalga qo'shilish"
        verbose_name_plural = "Kanalga qo'shilishlar"
        unique_together = [('channel', 'telegram_id')]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.telegram_id} → {self.channel.title}"


class Broadcast(models.Model):
    """Bot orqali yuborilgan reklama va uning natijasi."""

    class Kind(models.TextChoices):
        TEXT = 'text', "Matn"
        PHOTO = 'photo', "Rasm"
        VIDEO = 'video', "Video"
        DOCUMENT = 'document', "Fayl"

    text = models.TextField("Matn", blank=True)
    kind = models.CharField("Turi", max_length=20, choices=Kind.choices, default=Kind.TEXT)
    file_id = models.CharField("Telegram fayl id", max_length=300, blank=True)
    #: [{"label": "Saytga o'tish", "url": "https://..."}]
    buttons = models.JSONField("Tugmalar", default=list, blank=True)

    total = models.PositiveIntegerField("Jami qabul qiluvchi", default=0)
    sent = models.PositiveIntegerField("Yetkazildi", default=0)
    failed = models.PositiveIntegerField("Yetmadi", default=0)
    blocked = models.PositiveIntegerField("Botni bloklaganlar", default=0)

    created_by = models.BigIntegerField("Yuborgan admin", null=True, blank=True)
    created_at = models.DateTimeField("Boshlangan", default=timezone.now)
    finished_at = models.DateTimeField("Tugagan", null=True, blank=True)

    class Meta:
        verbose_name = "Reklama"
        verbose_name_plural = "Reklamalar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_kind_display()} — {self.sent}/{self.total}"


class TelegramAuthCode(models.Model):
    """Bot bergan bir martalik kod.

    Foydalanuvchi botga raqamini yuboradi -> bot kod beradi ->
    foydalanuvchi kodni saytga kiritadi -> tizimga kiradi.
    """

    code = models.CharField("Kod", max_length=8, unique=True, db_index=True)
    user = models.ForeignKey('accounts.User', verbose_name="Foydalanuvchi",
                             on_delete=models.CASCADE, related_name='auth_codes')

    telegram_id = models.BigIntegerField("Telegram ID")
    created_at = models.DateTimeField("Yaratilgan", default=timezone.now)
    used_at = models.DateTimeField("Ishlatilgan", null=True, blank=True)

    class Meta:
        verbose_name = "Telegram kod"
        verbose_name_plural = "Telegram kodlar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} — {self.user.full_name}"

    @property
    def is_expired(self):
        """Kod 5 daqiqa amal qiladi."""
        return timezone.now() - self.created_at > timedelta(minutes=5)

    @property
    def is_valid(self):
        return self.used_at is None and not self.is_expired
