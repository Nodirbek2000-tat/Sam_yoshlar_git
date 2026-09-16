"""Frontend (Next.js) uchun serializerlar.

Qoida: API faqat frontendga kerak bo'lgan maydonlarni beradi.
Telefon, email kabi shaxsiy ma'lumotlar ochiq ro'yxatlarga tushmaydi.
"""
import re

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from rest_framework import serializers

from apps.abroad.models import Peer
from apps.business.models import BusinessProfile, GalleryImage
from apps.content.models import Announcement, Event, News
from apps.initiatives.directions import DIRECTIONS, get_direction
from apps.initiatives.models import (Initiative, InitiativeComment, Organization,
                                     Problem, Solution)
from apps.startups.models import Startup

User = get_user_model()


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

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone', 'role', 'role_display',
                  'region', 'region_display', 'district', 'bio', 'avatar',
                  'initials', 'telegram_username', 'is_verified', 'is_panel_admin',
                  'onboarding', 'age', 'study_location', 'capabilities']
        read_only_fields = ['id', 'email', 'phone', 'telegram_username', 'is_verified', 'age']

    capabilities = serializers.SerializerMethodField()

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
        fields = ['full_name', 'role', 'region', 'district', 'bio', 'study_location']

    def validate_role(self, value):
        from apps.accounts.models import Role
        # Adminlikni o'zi tanlab ololmaydi
        if value == Role.ADMIN:
            raise serializers.ValidationError("Bu rolni tanlab bo'lmaydi.")
        return value


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


class PanelNewsSerializer(serializers.ModelSerializer):
    """Panel uchun: ro'yxatda ham, qo'shish-tahrirlashda ham shu ishlatiladi."""

    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    author_display = serializers.CharField(source='display_author', read_only=True)

    class Meta:
        model = News
        fields = ['id', 'slug', 'title', 'category', 'category_display', 'excerpt', 'body',
                  'image', 'image_url', 'author_name', 'author_display', 'published_at',
                  'is_published', 'is_featured', 'views', 'created_at']
        read_only_fields = ['id', 'slug', 'views', 'created_at']

    def get_image_url(self, obj):
        return absolute(self.context.get('request'), obj.image)

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Sarlavha juda qisqa.")
        return value


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
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    icon = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Announcement
        fields = ['id', 'slug', 'title', 'type', 'type_display', 'icon', 'body',
                  'file', 'file_url', 'posted_at', 'deadline', 'is_active',
                  'is_expired', 'created_at']
        read_only_fields = ['id', 'slug', 'created_at']

    def get_file_url(self, obj):
        return absolute(self.context.get('request'), obj.file)

    def validate(self, attrs):
        posted = attrs.get('posted_at') or getattr(self.instance, 'posted_at', None)
        deadline = attrs.get('deadline') or getattr(self.instance, 'deadline', None)
        if posted and deadline and deadline < posted:
            raise serializers.ValidationError(
                {'deadline': "Muddat e'lon sanasidan oldin bo'lishi mumkin emas."})
        return attrs


class NewsDetailSerializer(NewsListSerializer):
    class Meta(NewsListSerializer.Meta):
        fields = NewsListSerializer.Meta.fields + ['body', 'author_name']


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

    class Meta:
        model = Announcement
        fields = ['id', 'slug', 'title', 'type', 'type_display', 'icon', 'body',
                  'posted_at', 'deadline', 'is_active', 'is_expired', 'file']

    def get_file(self, obj):
        return absolute(self.context.get('request'), obj.file)


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
                  'status', 'status_display', 'admin_note', 'created_at']
        read_only_fields = ['id', 'status', 'admin_note', 'created_at']

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
