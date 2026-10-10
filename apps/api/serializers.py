"""Frontend (Next.js) uchun serializerlar.

Qoida: API faqat frontendga kerak bo'lgan maydonlarni beradi.
Telefon, email kabi shaxsiy ma'lumotlar ochiq ro'yxatlarga tushmaydi.
"""
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from rest_framework import serializers

from apps.abroad.models import Peer
from apps.business.models import BusinessProfile, GalleryImage
from apps.content.models import (NEWS_PHOTO_LIMIT, NEWS_VIDEO_EXTENSIONS, NEWS_VIDEO_MAX_MB,
                                 Announcement, Event, News, NewsPhoto)
from apps.initiatives.directions import DIRECTIONS, get_direction
from apps.initiatives.models import (Initiative, InitiativeComment, Organization,
                                     Problem, Solution)
from apps.startups.models import OfficeStartup, Startup

User = get_user_model()


def check_social(status, place, required=False):
    """Ijtimoiy holat va ta'lim muassasasi: xatolar lug'ati (bo'sh bo'lsa — hammasi joyida).

    Talaba yoki maktab o'quvchisi bo'lsa — o'qish joyining nomi majburiy.
    """
    from apps.accounts.models import SocialStatus

    errors = {}
    if required and not status:
        errors['social_status'] = "Ijtimoiy holatingizni tanlang."
    if status == SocialStatus.STUDENT and not place:
        errors['education_place'] = "Universitetingiz nomini kiriting."
    if status == SocialStatus.SCHOOL and not place:
        errors['education_place'] = "Maktabingiz nomini kiriting."
    return errors


def save_social(user, status, place):
    """Holat foydalanuvchida saqlanadi — keyingi startaplarda qayta so'ralmaydi."""
    from apps.accounts.models import STUDYING_STATUSES

    if not status:
        return
    user.social_status = status
    # O'qimaydigan holatda eski o'qish joyi qolib ketmasin
    user.education_place = place if status in STUDYING_STATUSES else ''
    user.save(update_fields=['social_status', 'education_place'])


def absolute(request, file_field):
    """Rasm uchun to'liq URL.

    Serverda sayt Django'ga ichki `http://web:8000` orqali murojaat qiladi —
    so'rovdan yasalgan manzil brauzerda ochilmaydi. Shuning uchun `SITE_URL`
    berilgan bo'lsa, manzil doim tashqi domen bilan yasaladi.
    """
    if not file_field:
        return None
    url = file_field.url

    from django.conf import settings

    site = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if site:
        return f"{site}{url}"
    if request is None:
        return url
    # Ichki xost bo'lsa (SITE_URL yo'q) — nisbiy manzil, nginx o'zi beradi
    if request.get_host().split(':')[0] == 'web':
        return url
    return request.build_absolute_uri(url)


# --------------------------------------------------------------------------
# Foydalanuvchi
# --------------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    region_display = serializers.CharField(source='get_region_display', read_only=True)
    initials = serializers.CharField(read_only=True)
    is_panel_admin = serializers.SerializerMethodField()
    onboarding = serializers.SerializerMethodField()
    social_status_display = serializers.CharField(source='get_social_status_display',
                                                  read_only=True)

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone', 'role', 'role_display',
                  'region', 'region_display', 'district', 'bio', 'avatar',
                  'initials', 'telegram_username', 'telegram_linked', 'is_verified',
                  'is_panel_admin', 'onboarding', 'age', 'study_location', 'capabilities',
                  'social_status', 'social_status_display', 'education_place',
                  'organization_name', 'unread_notifications', 'pending_feedback']
        read_only_fields = ['id', 'email', 'phone', 'telegram_username', 'is_verified', 'age']

    capabilities = serializers.SerializerMethodField()
    telegram_linked = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    unread_notifications = serializers.SerializerMethodField()
    pending_feedback = serializers.SerializerMethodField()

    def get_unread_notifications(self, obj):
        """Sarlavhadagi qo'ng'iroqcha uchun — o'qilmagan bildirishnomalar soni."""
        return obj.notifications.filter(is_read=False).count()

    def get_pending_feedback(self, obj):
        """Startap egasidan investor bilan suhbat natijasi so'ralishi kerakmi."""
        from .offer_views import pending_feedback

        return pending_feedback(obj)

    def get_telegram_linked(self, obj):
        return obj.telegram_id is not None

    def get_organization_name(self, obj):
        """Tashkilot hisobi bo'lsa — tashkilotning nomi (aks holda bo'sh)."""
        from apps.accounts.models import Role
        from apps.accounts.org_link import organization_name

        return organization_name(obj) if obj.role == Role.ORGANIZATION else ''

    def get_capabilities(self, obj):
        """Bir odam bir nechta rolda bo'la oladi: nimasi borligi."""
        from apps.abroad.models import Peer
        from apps.business.models import BusinessProfile

        return {
            'business': BusinessProfile.objects.filter(user=obj).exists(),
            'startups': obj.startups.count(),
            'peer': Peer.objects.filter(user=obj).exists(),
        }

    def get_avatar(self, obj):
        return absolute(self.context.get('request'), obj.avatar)

    def get_is_panel_admin(self, obj):
        from apps.panel.mixins import is_panel_admin
        return is_panel_admin(obj)

    def get_onboarding(self, obj):
        from .onboarding import onboarding_step
        return onboarding_step(obj)


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Ro'yxatdan o'tishni yakunlash: rol va hudud tanlash."""

    class Meta:
        model = User
        fields = ['full_name', 'role', 'region', 'district', 'bio', 'study_location',
                  'social_status', 'education_place']

    def validate_education_place(self, value):
        return value.strip()

    def validate(self, attrs):
        if 'social_status' in attrs or 'education_place' in attrs:
            status = attrs.get('social_status', self.instance.social_status if self.instance else '')
            place = attrs.get('education_place',
                              self.instance.education_place if self.instance else '')
            errors = check_social(status, place)
            if errors:
                raise serializers.ValidationError(errors)
            from apps.accounts.models import STUDYING_STATUSES

            if 'social_status' in attrs and status not in STUDYING_STATUSES:
                attrs['education_place'] = ''
        return attrs

    def validate_role(self, value):
        from apps.accounts.models import Role

        current = self.instance.role if self.instance else None

        # Tashkilot hisobini biz ochamiz — u boshqa rolga o'tmaydi
        if current == Role.ORGANIZATION and value != Role.ORGANIZATION:
            raise serializers.ValidationError("Tashkilot hisobining rolini o'zgartirib bo'lmaydi.")
        # Adminlik va tashkilotni o'zi tanlab ololmaydi
        if value in (Role.ADMIN, Role.ORGANIZATION) and value != current:
            raise serializers.ValidationError("Bu rolni tanlab bo'lmaydi.")
        return value

    def validate_district(self, value):
        """Faqat Samarqand viloyatining tuman va shaharlari."""
        from apps.core.constants import district_label

        if not value:
            return ''
        label = district_label(value)
        if not label:
            raise serializers.ValidationError("Bunday tuman yoki shahar yo'q.")
        return label

    def update(self, instance, validated_data):
        from apps.core.constants import Region

        # Tuman tanlangan bo'lsa viloyat ham aniq
        if validated_data.get('district'):
            validated_data['region'] = Region.SAMARQAND
        return super().update(instance, validated_data)


# --------------------------------------------------------------------------
# Kontent
# --------------------------------------------------------------------------

class NewsListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = News
        fields = ['id', 'slug', 'title', 'excerpt', 'category', 'category_display',
                  'image', 'published_at', 'views', 'is_featured']

    def get_image(self, obj):
        return absolute(self.context.get('request'), obj.image)


def news_photos(request, news):
    return [{'id': photo.pk, 'url': absolute(request, photo.image)} for photo in news.photos.all()]


class PanelNewsSerializer(serializers.ModelSerializer):
    """Panel uchun: ro'yxatda ham, qo'shish-tahrirlashda ham shu ishlatiladi.

    Qo'shimcha rasmlar `new_photos` (bir nechta fayl) bilan qo'shiladi,
    `remove_photos` (id ro'yxati) bilan o'chadi. Video bitta, 25 MB gacha.
    """

    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()
    video = serializers.FileField(required=False, allow_null=True, write_only=True)
    video_url = serializers.SerializerMethodField()
    remove_video = serializers.BooleanField(required=False, write_only=True)
    photos = serializers.SerializerMethodField()
    new_photos = serializers.ListField(child=serializers.ImageField(), required=False,
                                       write_only=True)
    remove_photos = serializers.ListField(child=serializers.IntegerField(), required=False,
                                          write_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    author_display = serializers.CharField(source='display_author', read_only=True)

    class Meta:
        model = News
        fields = ['id', 'slug', 'title', 'category', 'category_display', 'excerpt', 'body',
                  'image', 'image_url', 'video', 'video_url', 'remove_video', 'photos',
                  'new_photos', 'remove_photos', 'author_name', 'author_display',
                  'published_at', 'is_published', 'is_featured', 'views', 'created_at']
        read_only_fields = ['id', 'slug', 'views', 'created_at']

    def get_image_url(self, obj):
        return absolute(self.context.get('request'), obj.image)

    def get_video_url(self, obj):
        return absolute(self.context.get('request'), obj.video)

    def get_photos(self, obj):
        return news_photos(self.context.get('request'), obj)

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Sarlavha juda qisqa.")
        return value

    def validate_video(self, file):
        if not file:
            return file
        extension = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
        if extension not in NEWS_VIDEO_EXTENSIONS:
            raise serializers.ValidationError("Video MP4, WEBM yoki MOV formatida bo'lsin.")
        if file.size > NEWS_VIDEO_MAX_MB * 1024 * 1024:
            raise serializers.ValidationError(f"Video {NEWS_VIDEO_MAX_MB} MB dan oshmasin.")
        return file

    def validate_new_photos(self, files):
        for file in files:
            validate_image_size(file, limit_mb=10)
        return files

    def validate(self, attrs):
        kept = 0
        if self.instance is not None:
            removing = set(attrs.get('remove_photos') or [])
            kept = self.instance.photos.exclude(pk__in=removing).count()
        added = len(attrs.get('new_photos') or [])
        if kept + added > NEWS_PHOTO_LIMIT:
            raise serializers.ValidationError(
                {'new_photos': f"Ko'pi bilan {NEWS_PHOTO_LIMIT} ta qo'shimcha rasm. "
                               f"Yana {max(NEWS_PHOTO_LIMIT - kept, 0)} ta qo'shish mumkin."})
        return attrs

    def _media(self, item, new_photos, remove_photos, old_video=''):
        if remove_photos:
            for photo in item.photos.filter(pk__in=remove_photos):
                photo.image.delete(save=False)
                photo.delete()
        if new_photos:
            start = (item.photos.order_by('-order').values_list('order', flat=True).first() or 0) + 1
            for index, file in enumerate(new_photos):
                NewsPhoto.objects.create(news=item, image=file, order=start + index)
        # Almashtirilgan yoki olib tashlangan video diskda qolib ketmasin
        if old_video and old_video != item.video.name:
            item.video.storage.delete(old_video)

    def create(self, validated_data):
        new_photos = validated_data.pop('new_photos', [])
        validated_data.pop('remove_photos', None)
        validated_data.pop('remove_video', None)
        item = super().create(validated_data)
        self._media(item, new_photos, [])
        return item

    def update(self, instance, validated_data):
        new_photos = validated_data.pop('new_photos', [])
        remove_photos = validated_data.pop('remove_photos', [])
        old_video = instance.video.name or ''
        if validated_data.pop('remove_video', False) and 'video' not in validated_data:
            validated_data['video'] = None
        item = super().update(instance, validated_data)
        self._media(item, new_photos, remove_photos, old_video)
        return item


class PanelEventSerializer(serializers.ModelSerializer):
    """Panel uchun tadbir: ro'yxat va tahrirlash bitta shakl."""

    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()
    region_display = serializers.CharField(source='get_region_display', read_only=True)
    registered_count = serializers.SerializerMethodField()
    is_past = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = ['id', 'slug', 'title', 'description', 'starts_at', 'ends_at',
                  'location', 'region', 'region_display', 'capacity', 'image',
                  'image_url', 'is_published', 'registered_count', 'is_past',
                  'created_at']
        read_only_fields = ['id', 'slug', 'created_at']

    def get_image_url(self, obj):
        return absolute(self.context.get('request'), obj.image)

    def get_registered_count(self, obj):
        return obj.registered_count

    def validate(self, attrs):
        starts = attrs.get('starts_at') or getattr(self.instance, 'starts_at', None)
        ends = attrs.get('ends_at') or getattr(self.instance, 'ends_at', None)
        if starts and ends and ends < starts:
            raise serializers.ValidationError(
                {'ends_at': "Tugash vaqti boshlanishdan oldin bo'lishi mumkin emas."})
        return attrs


class PanelAnnouncementSerializer(serializers.ModelSerializer):
    """Panel uchun e'lon."""

    file = serializers.FileField(required=False, allow_null=True)
    file_url = serializers.SerializerMethodField()
    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()
    # Tahrirlashda rasmni olib tashlash uchun belgi
    remove_image = serializers.BooleanField(required=False, write_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    icon = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Announcement
        fields = ['id', 'slug', 'title', 'type', 'type_display', 'icon', 'body',
                  'image', 'image_url', 'remove_image', 'file', 'file_url', 'apply_url',
                  'posted_at', 'deadline', 'is_active', 'is_expired', 'created_at']
        read_only_fields = ['id', 'slug', 'created_at']

    def get_file_url(self, obj):
        return absolute(self.context.get('request'), obj.file)

    def get_image_url(self, obj):
        return absolute(self.context.get('request'), obj.image)

    def _drop_image(self, instance, validated_data):
        if validated_data.pop('remove_image', False) and 'image' not in validated_data:
            if instance is not None and instance.image:
                instance.image.delete(save=False)
            validated_data['image'] = ''

    def create(self, validated_data):
        validated_data.pop('remove_image', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        old_image = instance.image.name if instance.image else ''
        self._drop_image(instance, validated_data)
        item = super().update(instance, validated_data)
        # Yangi rasm yuklansa — eskisi diskda qolib ketmasin
        if old_image and item.image.name != old_image:
            item.image.storage.delete(old_image)
        return item

    def validate(self, attrs):
        posted = attrs.get('posted_at') or getattr(self.instance, 'posted_at', None)
        deadline = attrs.get('deadline') or getattr(self.instance, 'deadline', None)
        if posted and deadline and deadline < posted:
            raise serializers.ValidationError(
                {'deadline': "Muddat e'lon sanasidan oldin bo'lishi mumkin emas."})
        return attrs


class NewsDetailSerializer(NewsListSerializer):
    photos = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()

    class Meta(NewsListSerializer.Meta):
        fields = NewsListSerializer.Meta.fields + ['body', 'author_name', 'photos', 'video']

    def get_photos(self, obj):
        return [photo['url'] for photo in news_photos(self.context.get('request'), obj)]

    def get_video(self, obj):
        return absolute(self.context.get('request'), obj.video)


class EventListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    region_display = serializers.CharField(source='get_region_display', read_only=True)
    registered_count = serializers.IntegerField(read_only=True)
    seats_left = serializers.IntegerField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    fill_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Event
        fields = ['id', 'slug', 'title', 'starts_at', 'ends_at', 'location',
                  'region', 'region_display', 'capacity', 'image',
                  'registered_count', 'seats_left', 'is_past', 'is_full', 'fill_percent']

    def get_image(self, obj):
        return absolute(self.context.get('request'), obj.image)


class EventDetailSerializer(EventListSerializer):
    is_registered = serializers.SerializerMethodField()

    class Meta(EventListSerializer.Meta):
        fields = EventListSerializer.Meta.fields + ['description', 'is_registered']

    def get_is_registered(self, obj):
        request = self.context.get('request')
        return obj.is_registered(request.user) if request else False


class AnnouncementSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    icon = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    file = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'slug', 'title', 'type', 'type_display', 'icon', 'body', 'image',
                  'apply_url', 'posted_at', 'deadline', 'is_active', 'is_expired', 'file']

    def get_file(self, obj):
        return absolute(self.context.get('request'), obj.file)

    def get_image(self, obj):
        return absolute(self.context.get('request'), obj.image)


# --------------------------------------------------------------------------
# Tashabbuslar
# --------------------------------------------------------------------------

class DirectionSerializer(serializers.Serializer):
    """14 yo'nalish — sahna chizish uchun barcha metama'lumot bilan."""

    id = serializers.CharField()
    scene = serializers.CharField()
    name = serializers.CharField()
    title = serializers.CharField()
    tagline = serializers.CharField()
    color = serializers.CharField()
    accent = serializers.CharField()
    max = serializers.IntegerField()
    unit = serializers.CharField()
    icon = serializers.CharField()
    votes = serializers.IntegerField(required=False)
    ideas = serializers.IntegerField(required=False)


class InitiativeListSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    kind_icon = serializers.CharField(read_only=True)
    region_display = serializers.CharField(source='get_region_display', read_only=True)
    author_label = serializers.CharField(read_only=True)
    direction_info = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    voted = serializers.SerializerMethodField()

    class Meta:
        model = Initiative
        fields = ['id', 'direction', 'direction_info', 'kind', 'kind_display', 'kind_icon',
                  'title', 'summary', 'description', 'expected_result',
                  'author_label', 'region', 'region_display',
                  'vote_count', 'comment_count', 'voted', 'created_at']

    def get_direction_info(self, obj):
        return DirectionSerializer(get_direction(obj.direction)).data

    def get_comment_count(self, obj):
        value = getattr(obj, 'comment_total', None)
        return value if value is not None else obj.comments.count()

    def get_voted(self, obj):
        return obj.pk in self.context.get('voted_ids', set())


class InitiativeCommentSerializer(serializers.ModelSerializer):
    author_label = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)

    class Meta:
        model = InitiativeComment
        fields = ['id', 'author_id', 'author_name', 'author_label', 'initials', 'text',
                  'created_at']
        read_only_fields = ['id', 'author_label', 'initials', 'created_at']


class InitiativeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Initiative
        # `id` javobda qaytadi — front yangi tashabbusga havola bera olsin
        fields = ['id', 'direction', 'kind', 'title', 'summary', 'description',
                  'expected_result', 'author_name', 'author_phone', 'region']
        read_only_fields = ['id']

    def validate_direction(self, value):
        if value not in {item['id'] for item in DIRECTIONS}:
            raise serializers.ValidationError("Bunday yo'nalish yo'q.")
        return value


# --------------------------------------------------------------------------
# Tashkilot muammolari
# --------------------------------------------------------------------------

class OrganizationSerializer(serializers.ModelSerializer):
    sphere_display = serializers.CharField(source='get_sphere_display', read_only=True)
    region_display = serializers.CharField(source='get_region_display', read_only=True)

    class Meta:
        model = Organization
        fields = ['id', 'name', 'sphere', 'sphere_display', 'region', 'region_display']


class ProblemSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    icon = serializers.CharField(read_only=True)
    question = serializers.CharField(read_only=True)
    age_label = serializers.CharField(read_only=True)
    solution_count = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = ['id', 'organization', 'category', 'category_display', 'icon',
                  'question', 'description', 'age_label', 'solution_count', 'created_at']

    def get_solution_count(self, obj):
        value = getattr(obj, 'solution_total', None)
        return value if value is not None else obj.solutions.count()


class ProblemCreateSerializer(serializers.ModelSerializer):
    """Tashkilot muammo yozganda. Tashkilot so'rovdan emas, hisobdan olinadi."""

    class Meta:
        model = Problem
        fields = ['id', 'category', 'description']
        read_only_fields = ['id']

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 40:
            raise serializers.ValidationError(
                "Muammoni batafsilroq yozing — kamida bir necha jumla.")
        return value


class SolutionSerializer(serializers.ModelSerializer):
    liked = serializers.SerializerMethodField()

    class Meta:
        model = Solution
        # `author_id` — profilga havola uchun (muallif ro'yxatdan o'tgan bo'lsa)
        fields = ['id', 'author_id', 'author_name', 'title', 'description', 'technologies',
                  'expected_result', 'like_count', 'liked', 'created_at']
        # Muallif nomi kirgan foydalanuvchidan olinadi, so'rovdan emas
        read_only_fields = ['id', 'author_name', 'like_count', 'created_at']

    def get_liked(self, obj):
        # Ro'yxatni chizishdan oldin ko'rish: qaysi takliflar allaqachon layk qilingan
        return obj.pk in self.context.get('liked_ids', set())


# --------------------------------------------------------------------------
# Chet eldagi tengdoshlar va startaplar
# --------------------------------------------------------------------------

def normalize_website(value):
    """`mysite.uz` ham qabul qilinsin — boshiga `https://` qo'shamiz."""
    value = (value or '').strip()
    if not value:
        return ''
    if not re.match(r'^https?://', value, re.I):
        value = f"https://{value}"
    try:
        URLValidator()(value)
    except DjangoValidationError:
        raise serializers.ValidationError("Sayt manzilini tekshiring.")
    return value


def validate_image_size(file, limit_mb=5):
    if file and file.size > limit_mb * 1024 * 1024:
        raise serializers.ValidationError(f"Rasm {limit_mb} MB dan oshmasin.")
    return file


class StartupSetupSerializer(serializers.ModelSerializer):
    """Startupperdan so'raladigan anketa — ro'yxatdan o'tishda ham,
    kabinetdagi «Startapim» bo'limida ham shu ishlatiladi."""

    logo = serializers.ImageField(required=False, allow_null=True, write_only=True)
    pitch_file = serializers.FileField(required=False, allow_null=True, write_only=True)
    website = serializers.CharField(required=False, allow_blank=True, max_length=200)
    # Egasining ijtimoiy holati — foydalanuvchida saqlanadi, startapda emas
    social_status = serializers.ChoiceField(choices=[], required=False, allow_blank=True,
                                            write_only=True)
    education_place = serializers.CharField(required=False, allow_blank=True, max_length=200,
                                            write_only=True)

    logo_url = serializers.SerializerMethodField()
    pitch_url = serializers.SerializerMethodField()
    sphere_display = serializers.CharField(source='get_sphere_display', read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Startup
        fields = ['id', 'name', 'sphere', 'sphere_display', 'stage', 'stage_display',
                  'about', 'problem_solved', 'team_size', 'needed_investment',
                  'website', 'logo', 'logo_url', 'pitch_file', 'pitch_url',
                  'status', 'status_display', 'admin_note', 'created_at',
                  'social_status', 'education_place']
        read_only_fields = ['id', 'status', 'admin_note', 'created_at']

    def __init__(self, *args, **kwargs):
        from apps.accounts.models import SocialStatus

        super().__init__(*args, **kwargs)
        self.fields['social_status'].choices = SocialStatus.choices

    def _owner(self):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return user if user is not None and user.is_authenticated else None

    def _save_owner_social(self, validated_data):
        status = validated_data.pop('social_status', '')
        place = validated_data.pop('education_place', '').strip()
        owner = self._owner()
        if owner is not None:
            save_social(owner, status, place)

    def create(self, validated_data):
        self._save_owner_social(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._save_owner_social(validated_data)
        return super().update(instance, validated_data)

    def get_logo_url(self, obj):
        return absolute(self.context.get('request'), obj.logo)

    def get_pitch_url(self, obj):
        return absolute(self.context.get('request'), obj.pitch_file)

    def validate_about(self, value):
        value = value.strip()
        if len(value) < 30:
            raise serializers.ValidationError(
                "Startapingizni biroz batafsilroq tanishtiring.")
        return value

    def validate_team_size(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Kamida bir kishi.")
        return value

    def validate_website(self, value):
        return normalize_website(value)

    def validate_logo(self, value):
        return validate_image_size(value)

    def validate_pitch_file(self, value):
        if value and value.size > 20 * 1024 * 1024:
            raise serializers.ValidationError("Pitch fayl 20 MB dan oshmasin.")
        return value

    def validate(self, attrs):
        # Logotip majburiy: ro'yxatda startap shu bilan tanilinadi
        if not attrs.get('logo') and not (self.instance and self.instance.logo):
            raise serializers.ValidationError({'logo': "Logotipni yuklang."})

        # Yangi startap qo'shilganda holat hali ma'lum bo'lmasa — so'raladi
        owner = self._owner()
        required = self.instance is None and owner is not None and not owner.social_status
        errors = check_social(attrs.get('social_status', ''),
                              attrs.get('education_place', '').strip(), required=required)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class GalleryImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = GalleryImage
        fields = ['id', 'url', 'caption']

    def get_url(self, obj):
        return absolute(self.context.get('request'), obj.image)


class BusinessSetupSerializer(serializers.ModelSerializer):
    """Tadbirkordan so'raladigan biznes ma'lumoti — ro'yxatdan o'tishda ham,
    kabinetdagi «Biznesim» bo'limida ham."""

    logo = serializers.ImageField(required=False, allow_null=True, write_only=True)
    website = serializers.CharField(required=False, allow_blank=True, max_length=200)

    logo_url = serializers.SerializerMethodField()
    sphere_display = serializers.CharField(source='get_sphere_display', read_only=True)
    region_display = serializers.CharField(source='get_region_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    gallery = GalleryImageSerializer(many=True, read_only=True)

    class Meta:
        model = BusinessProfile
        fields = ['id', 'name', 'sphere', 'sphere_display', 'stir', 'founded_year',
                  'employees', 'region', 'region_display', 'district', 'address',
                  'description', 'website', 'phone', 'email', 'telegram', 'instagram',
                  'logo', 'logo_url', 'gallery', 'status', 'status_display', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def get_logo_url(self, obj):
        return absolute(self.context.get('request'), obj.logo)

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 30:
            raise serializers.ValidationError("Biznesingizni biroz batafsilroq yozing.")
        return value

    def validate_founded_year(self, value):
        if value and not 1900 <= value <= timezone.now().year:
            raise serializers.ValidationError("Yilni tekshiring.")
        return value

    def validate_employees(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Kamida bir kishi.")
        return value

    def validate_stir(self, value):
        value = (value or '').strip().replace(' ', '')
        if value and (not value.isdigit() or len(value) != 9):
            raise serializers.ValidationError("STIR 9 ta raqamdan iborat bo'ladi.")
        return value

    def validate_website(self, value):
        return normalize_website(value)

    def validate_instagram(self, value):
        return (value or '').strip().lstrip('@')

    def validate_telegram(self, value):
        return (value or '').strip().lstrip('@')

    def validate_logo(self, value):
        return validate_image_size(value)

    def validate(self, attrs):
        if not attrs.get('logo') and not (self.instance and self.instance.logo):
            raise serializers.ValidationError({'logo': "Logotipni yuklang."})
        return attrs


# --------------------------------------------------------------------------
# Ochiq ro'yxatlar: tadbirkorlar va startaplar
# --------------------------------------------------------------------------

class PublicBusinessSerializer(serializers.ModelSerializer):
    """Ro'yxatdagi karta: logo, muqova (birinchi rasm), qisqa ma'lumot."""

    sphere_display = serializers.CharField(source='get_sphere_display', read_only=True)
    sphere_icon = serializers.CharField(read_only=True)
    region_display = serializers.CharField(source='get_region_display', read_only=True)
    logo_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    photo_count = serializers.SerializerMethodField()

    class Meta:
        model = BusinessProfile
        fields = ['id', 'name', 'sphere', 'sphere_display', 'sphere_icon', 'region',
                  'region_display', 'district', 'description', 'employees', 'founded_year',
                  'logo_url', 'cover_url', 'photo_count', 'created_at']

    def get_logo_url(self, obj):
        return absolute(self.context.get('request'), obj.logo)

    def get_cover_url(self, obj):
        photos = list(obj.gallery.all())
        return absolute(self.context.get('request'), photos[-1].image) if photos else None

    def get_photo_count(self, obj):
        return len(obj.gallery.all())


class PublicBusinessDetailSerializer(PublicBusinessSerializer):
    """Tadbirkor sahifasi: hamma rasm va aloqa."""

    gallery = GalleryImageSerializer(many=True, read_only=True)
    owner_name = serializers.SerializerMethodField()

    class Meta(PublicBusinessSerializer.Meta):
        fields = PublicBusinessSerializer.Meta.fields + [
            'address', 'website', 'phone', 'email', 'telegram', 'instagram',
            'gallery', 'owner_name']

    def get_owner_name(self, obj):
        return obj.user.full_name if obj.user_id else ''


class PublicStartupSerializer(serializers.ModelSerializer):
    sphere_display = serializers.CharField(source='get_sphere_display', read_only=True)
    sphere_icon = serializers.CharField(read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    region_display = serializers.CharField(source='get_region_display', read_only=True)
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Startup
        fields = ['id', 'name', 'sphere', 'sphere_display', 'sphere_icon', 'stage',
                  'stage_display', 'about', 'team_size', 'needed_investment',
                  'region', 'region_display', 'logo_url', 'created_at']

    def get_logo_url(self, obj):
        return absolute(self.context.get('request'), obj.logo)


class PublicStartupDetailSerializer(PublicStartupSerializer):
    pitch_url = serializers.SerializerMethodField()

    class Meta(PublicStartupSerializer.Meta):
        fields = PublicStartupSerializer.Meta.fields + [
            'problem_solved', 'website', 'pitch_url', 'full_name']

    def get_pitch_url(self, obj):
        return absolute(self.context.get('request'), obj.pitch_file)


class PeerSerializer(serializers.ModelSerializer):
    purpose_display = serializers.CharField(source='get_purpose_display', read_only=True)
    purpose_icon = serializers.CharField(read_only=True)
    country_name = serializers.CharField(source='get_country_display', read_only=True)
    country_short = serializers.CharField(source='flag', read_only=True)
    country_color = serializers.CharField(read_only=True)
    home_region_display = serializers.CharField(source='get_home_region_display',
                                                read_only=True)
    initials = serializers.CharField(read_only=True)
    photo = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()

    class Meta:
        model = Peer
        fields = ['id', 'full_name', 'country', 'country_name', 'country_short',
                  'country_color', 'city', 'home_region', 'home_region_display',
                  'purpose', 'purpose_display', 'purpose_icon', 'institution', 'field',
                  'since_year', 'course', 'achievements', 'about', 'can_help',
                  'telegram', 'email', 'phone', 'age', 'photo', 'initials', 'created_at']

    def get_photo(self, obj):
        return absolute(self.context.get('request'), obj.photo)

    def get_age(self, obj):
        return obj.user.age if obj.user_id else None


class PeerSetupSerializer(serializers.ModelSerializer):
    """Chet elda o'qiydigan yoshning anketasi — ro'yxatdan o'tishda ham,
    kabinetdagi «Tengdosh profilim» bo'limida ham shu ishlatiladi."""

    photo = serializers.ImageField(required=False, allow_null=True, write_only=True)
    photo_url = serializers.SerializerMethodField()
    country_name = serializers.CharField(source='get_country_display', read_only=True)

    class Meta:
        model = Peer
        fields = ['id', 'country', 'country_name', 'city', 'institution', 'course', 'field',
                  'achievements', 'phone', 'telegram', 'email', 'photo', 'photo_url',
                  'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']
        extra_kwargs = {
            'institution': {'required': True, 'allow_blank': False},
            'field': {'required': True, 'allow_blank': False},
            'course': {'required': True, 'allow_null': False},
            'phone': {'required': True, 'allow_blank': False},
        }

    def get_photo_url(self, obj):
        return absolute(self.context.get('request'), obj.photo)

    def validate_course(self, value):
        if value is None or not 1 <= value <= 7:
            raise serializers.ValidationError("Kurs 1 dan 7 gacha bo'ladi.")
        return value

    def validate_achievements(self, value):
        value = (value or '').strip()
        if len(value) > 300:
            raise serializers.ValidationError("Yutuqlar 300 ta belgidan oshmasin.")
        return value

    def validate_telegram(self, value):
        return (value or '').strip().lstrip('@')

    def validate_photo(self, value):
        return validate_image_size(value)

    def validate(self, attrs):
        has_photo = attrs.get('photo') or (self.instance and self.instance.photo)
        if not has_photo:
            raise serializers.ValidationError({'photo': "Rasmingizni yuklang."})
        return attrs


class StartupSerializer(serializers.ModelSerializer):
    sphere_display = serializers.CharField(source='get_sphere_display', read_only=True)
    sphere_icon = serializers.CharField(read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = Startup
        fields = ['id', 'name', 'sphere', 'sphere_display', 'sphere_icon',
                  'stage', 'stage_display', 'about', 'problem_solved',
                  'team_size', 'created_at']


# --------------------------------------------------------------------------
# Samarqand startuplar ofisi
# --------------------------------------------------------------------------

def office_age(item, today=None):
    """Yosh: tug'ilgan sanadan hisoblanadi, bo'lmasa — yozilgan yosh."""
    if item.birth_date:
        today = today or timezone.localdate()
        born = item.birth_date
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return item.age


def office_contact(item):
    """Telegram'da yozish havolasi: startapning o'z username'i bo'lsa — u, bo'lmasa — ofisning umumiy akkaunti."""
    username = item.telegram or settings.OFFICE_STARTUPS_TELEGRAM
    return f"https://t.me/{username}" if username else None


class OfficeStartupSerializer(serializers.ModelSerializer):
    """Ochiq sayt uchun. Telefon raqami alohida chiqmaydi — faqat Telegram havolasi."""

    sphere_display = serializers.CharField(source='get_sphere_display', read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    district_display = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    project_image = serializers.SerializerMethodField()
    contact_url = serializers.SerializerMethodField()

    class Meta:
        model = OfficeStartup
        fields = ['id', 'name', 'about', 'sphere', 'sphere_display', 'stage', 'stage_display',
                  'full_name', 'age', 'district', 'district_display', 'photo', 'project_image',
                  'contact_url', 'created_at']

    def get_district_display(self, obj):
        from apps.core.constants import district_label

        return district_label(obj.district) or obj.district

    def get_age(self, obj):
        return office_age(obj)

    def get_photo(self, obj):
        return absolute(self.context.get('request'), obj.photo)

    def get_project_image(self, obj):
        return absolute(self.context.get('request'), obj.project_image)

    def get_contact_url(self, obj):
        return office_contact(obj)


class PanelOfficeStartupSerializer(OfficeStartupSerializer):
    """Panel uchun: tahrirlash, rasmlarni almashtirish yoki olib tashlash."""

    photo_file = serializers.ImageField(source='photo', required=False, allow_null=True, write_only=True)
    project_image_file = serializers.ImageField(source='project_image', required=False,
                                                allow_null=True, write_only=True)
    remove_photo = serializers.BooleanField(required=False, write_only=True)
    remove_project_image = serializers.BooleanField(required=False, write_only=True)
    visible = serializers.BooleanField(source='is_published', read_only=True)

    class Meta(OfficeStartupSerializer.Meta):
        fields = OfficeStartupSerializer.Meta.fields + [
            'phone', 'telegram', 'birth_date', 'is_published', 'visible',
            'photo_file', 'project_image_file', 'remove_photo', 'remove_project_image',
        ]

    def validate_telegram(self, value):
        from apps.startups.office_import import parse_telegram

        value = (value or '').strip()
        if value and not parse_telegram(value):
            raise serializers.ValidationError("Telegram username noto'g'ri (masalan: @ali_startup).")
        return parse_telegram(value)

    def validate_phone(self, value):
        from apps.startups.office_import import parse_phone

        return parse_phone(value) if value else ''

    def _apply(self, instance, validated_data):
        old = {}
        for field, flag in (('photo', 'remove_photo'), ('project_image', 'remove_project_image')):
            current = getattr(instance, field) if instance else None
            if current:
                old[field] = current.name
            if validated_data.pop(flag, False) and field not in validated_data:
                validated_data[field] = ''
        return old

    def create(self, validated_data):
        validated_data.pop('remove_photo', None)
        validated_data.pop('remove_project_image', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        old = self._apply(instance, validated_data)
        item = super().update(instance, validated_data)
        # Almashtirilgan yoki olib tashlangan rasm diskda qolib ketmasin
        for field, name in old.items():
            if getattr(item, field).name != name:
                getattr(item, field).storage.delete(name)
        return item
