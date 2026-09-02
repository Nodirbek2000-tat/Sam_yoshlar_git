from django.contrib import admin
from django.utils import timezone

from .models import Appeal, Notification, Suggestion


@admin.register(Appeal)
class AppealAdmin(admin.ModelAdmin):
    list_display = ['subject', 'user', 'category', 'status', 'created_at']
    list_filter = ['status', 'category']
    search_fields = ['subject', 'message', 'user__email', 'user__full_name']
    list_editable = ['status']
    readonly_fields = ['created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        """Javob yozilganda javob vaqti va muallifi avtomatik to'ldiriladi."""
        if obj.response and not obj.responded_at:
            obj.responded_at = timezone.now()
            obj.responded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'votes', 'created_at']
    list_filter = ['status']
    search_fields = ['title', 'description']
    list_editable = ['status', 'votes']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'type', 'is_read', 'created_at']
    list_filter = ['type', 'is_read']
    search_fields = ['title', 'message', 'user__email']
