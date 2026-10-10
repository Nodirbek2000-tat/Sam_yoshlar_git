from django.contrib import admin

from .models import (Announcement, Event, EventRegistration, News, NewsPhoto, Poll, PollOption,
                     PollVote)


class NewsPhotoInline(admin.TabularInline):
    model = NewsPhoto
    extra = 0


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    inlines = [NewsPhotoInline]
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


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 0
    fields = ['order', 'name', 'mahalla', 'district', 'photo']


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ['title', 'ends_at', 'is_active', 'show_results', 'created_at']
    list_filter = ['is_active', 'show_results']
    search_fields = ['title', 'options__name']
    readonly_fields = ['slug']
    inlines = [PollOptionInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Nomzodlar so'rovnomadan keyin saqlanadi — botga e'lon shundan so'ng
        from apps.accounts.bot_feed import enqueue_poll
        enqueue_poll(form.instance)


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ['poll', 'option', 'user', 'created_at']
    list_filter = ['poll']
    search_fields = ['user__full_name', 'user__phone', 'option__name']
    raw_id_fields = ['user']
