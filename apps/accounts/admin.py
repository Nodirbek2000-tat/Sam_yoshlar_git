from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import TelegramAuthCode, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['full_name', 'phone', 'telegram_username', 'role', 'is_verified',
                    'is_active', 'date_joined']
    list_filter = ['role', 'is_verified', 'is_active', 'is_staff', 'region']
    search_fields = ['email', 'full_name', 'phone', 'telegram_username']
    ordering = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ("Shaxsiy ma'lumotlar", {'fields': ('full_name', 'phone', 'birth_date', 'avatar', 'bio')}),
        ("Telegram", {'fields': ('telegram_id', 'telegram_username')}),
        ("Hudud", {'fields': ('region', 'district')}),
        ("Ruxsatlar", {'fields': ('role', 'is_active', 'is_verified', 'is_staff', 'is_superuser',
                                  'groups', 'user_permissions')}),
        ("Sanalar", {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(TelegramAuthCode)
class TelegramAuthCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'user', 'telegram_id', 'created_at', 'used_at']
    search_fields = ['code', 'telegram_id', 'user__full_name', 'user__phone']
    readonly_fields = ['created_at', 'used_at']
