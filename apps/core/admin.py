from django.contrib import admin

from .models import Leader, SiteSetting, Task


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'phone', 'email']

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['text', 'order', 'is_active']
    list_editable = ['order', 'is_active']


@admin.register(Leader)
class LeaderAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'position', 'role', 'region', 'order', 'is_active']
    list_filter = ['role', 'is_active', 'region']
    search_fields = ['full_name', 'position']
    list_editable = ['order', 'is_active']
