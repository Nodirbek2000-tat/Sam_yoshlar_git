from django.contrib import admin

from .models import Announcement, Event, EventRegistration, News


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'published_at', 'is_published', 'is_featured', 'views']
    list_filter = ['category', 'is_published', 'is_featured', 'published_at']
    search_fields = ['title', 'excerpt', 'body']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    list_editable = ['is_published', 'is_featured']


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    fields = ['user', 'is_cancelled', 'attended', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'starts_at', 'location', 'capacity', 'registered_count', 'is_published']
    list_filter = ['is_published', 'region', 'starts_at']
    search_fields = ['title', 'description', 'location']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'starts_at'
    inlines = [EventRegistrationInline]

    @admin.display(description="Yozilganlar")
    def registered_count(self, obj):
        return obj.registered_count


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'is_cancelled', 'attended', 'created_at']
    list_filter = ['is_cancelled', 'attended']
    search_fields = ['user__full_name', 'user__email', 'event__title']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'posted_at', 'deadline', 'is_active']
    list_filter = ['type', 'is_active', 'posted_at']
    search_fields = ['title', 'body']
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ['is_active']
