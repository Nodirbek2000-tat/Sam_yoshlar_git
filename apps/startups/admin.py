from django.contrib import admin

from .models import FundedStartup, Laureate, OfficeStartup, Startup


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


@admin.register(OfficeStartup)
class OfficeStartupAdmin(admin.ModelAdmin):
    list_display = ['name', 'full_name', 'sphere', 'stage', 'district', 'is_published']
    list_filter = ['sphere', 'stage', 'is_published']
    search_fields = ['name', 'full_name', 'about']
    list_editable = ['is_published']


@admin.register(Laureate)
class LaureateAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'project_name', 'year', 'district', 'is_national_winner',
                    'is_published']
    list_filter = ['year', 'is_national_winner', 'is_published']
    search_fields = ['full_name', 'project_name']
    list_editable = ['is_published']


@admin.register(FundedStartup)
class FundedStartupAdmin(admin.ModelAdmin):
    list_display = ['name', 'amount', 'currency', 'funder', 'year', 'order', 'is_published']
    list_filter = ['currency', 'is_published']
    search_fields = ['name', 'founder', 'funder']
    list_editable = ['order', 'is_published']
