from django.contrib import admin

from .models import Startup


@admin.register(Startup)
class StartupAdmin(admin.ModelAdmin):
    list_display = ['name', 'full_name', 'sphere', 'stage', 'region', 'status', 'created_at']
    list_filter = ['sphere', 'stage', 'status', 'region']
    search_fields = ['name', 'full_name', 'email', 'phone', 'about']
    list_editable = ['status']
    date_hierarchy = 'created_at'

    fieldsets = (
        ("Ariza beruvchi", {'fields': ('user', 'full_name', 'phone', 'email', 'birth_date',
                                       'region', 'district')}),
        ("StartUp", {'fields': ('name', 'sphere', 'stage', 'about', 'problem_solved', 'team_size',
                                'needed_investment', 'pitch_file', 'logo', 'website')}),
        ("Ko'rib chiqish", {'fields': ('status', 'admin_note', 'is_public')}),
    )
