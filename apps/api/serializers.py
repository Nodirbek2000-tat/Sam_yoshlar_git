"""Frontend (Next.js) uchun serializerlar.

Qoida: API faqat frontendga kerak bo'lgan maydonlarni beradi.
Telefon, email kabi shaxsiy ma'lumotlar ochiq ro'yxatlarga tushmaydi.
"""
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.abroad.models import Peer
from apps.content.models import Announcement, Event, News
from apps.initiatives.directions import DIRECTIONS, get_direction
from apps.initiatives.models import (Initiative, InitiativeComment, Organization,
                                     Problem, Solution)
from apps.business.models import BusinessProfile
from apps.startups.models import Startup

User = get_user_model()


def absolute(request, file_field):
    """Rasm uchun to'liq URL — frontend boshqa domenda turadi."""
    if not file_field:
        return None
    url = file_field.url
    return request.build_absolute_uri(url) if request else url


# --------------------------------------------------------------------------
# Foydalanuvchi
# --------------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    region_display = serializers.CharField(source='get_region_display', read_only=True)
    initials = serializers.CharField(read_only=True)
    is_panel_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone', 'role', 'role_display',
                  'region', 'region_display', 'district', 'bio', 'avatar',
                  'initials', 'telegram_username', 'is_verified', 'is_panel_admin']
        read_only_fields = ['id', 'email', 'phone', 'telegram_username', 'is_verified']

    def get_avatar(self, obj):
        return absolute(self.context.get('request'), obj.avatar)

    def get_is_panel_admin(self, obj):
        from apps.panel.mixins import is_panel_admin
        return is_panel_admin(obj)


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Ro'yxatdan o'tishni yakunlash: rol va hudud tanlash."""

    class Meta:
        model = User
        fields = ['full_name', 'role', 'region', 'district', 'bio']

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
        fields = ['id', 'author_name', 'author_label', 'initials', 'text', 'created_at']
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
        fields = ['id', 'author_name', 'title', 'description', 'technologies',
                  'expected_result', 'like_count', 'liked', 'created_at']
        # Muallif nomi kirgan foydalanuvchidan olinadi, so'rovdan emas
        read_only_fields = ['id', 'author_name', 'like_count', 'created_at']

    def get_liked(self, obj):
        # Ro'yxatni chizishdan oldin ko'rish: qaysi takliflar allaqachon layk qilingan
        return obj.pk in self.context.get('liked_ids', set())


# --------------------------------------------------------------------------
# Chet eldagi tengdoshlar va startaplar
# --------------------------------------------------------------------------

class StartupSetupSerializer(serializers.ModelSerializer):
    """Ro'yxatdan o'tgan startupperdan so'raladigan eng zarur ma'lumot.

    Anketaning to'liq shakli kabinetda to'ldiriladi; bu yerda faqat
    startapni ro'yxatga qo'yish uchun yetarli maydonlar bor.
    """

    class Meta:
        model = Startup
        fields = ['id', 'name', 'sphere', 'stage', 'about', 'problem_solved', 'team_size']
        read_only_fields = ['id']

    def validate_about(self, value):
        value = value.strip()
        if len(value) < 30:
            raise serializers.ValidationError(
                "Startapingizni biroz batafsilroq tanishtiring.")
        return value


class BusinessSetupSerializer(serializers.ModelSerializer):
    """Tadbirkordan so'raladigan biznes ma'lumoti."""

    class Meta:
        model = BusinessProfile
        fields = ['id', 'name', 'sphere', 'founded_year', 'employees', 'description']
        read_only_fields = ['id']

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 30:
            raise serializers.ValidationError("Biznesingizni biroz batafsilroq yozing.")
        return value

    def validate_founded_year(self, value):
        if value and not 1900 <= value <= timezone.now().year:
            raise serializers.ValidationError("Yilni tekshiring.")
        return value


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

    class Meta:
        model = Peer
        fields = ['id', 'full_name', 'country', 'country_name', 'country_short',
                  'country_color', 'city', 'home_region', 'home_region_display',
                  'purpose', 'purpose_display', 'purpose_icon', 'institution', 'field',
                  'since_year', 'about', 'can_help', 'photo', 'initials', 'created_at']

    def get_photo(self, obj):
        return absolute(self.context.get('request'), obj.photo)


class StartupSerializer(serializers.ModelSerializer):
    sphere_display = serializers.CharField(source='get_sphere_display', read_only=True)
    sphere_icon = serializers.CharField(read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = Startup
        fields = ['id', 'name', 'sphere', 'sphere_display', 'sphere_icon',
                  'stage', 'stage_display', 'about', 'problem_solved',
                  'team_size', 'created_at']
