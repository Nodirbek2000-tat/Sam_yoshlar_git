from django.contrib import admin

from .models import Peer


@admin.register(Peer)
class PeerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'country', 'city', 'purpose', 'institution', 'status',
                    'is_published']
    list_filter = ['country', 'purpose', 'status', 'is_published']
    search_fields = ['full_name', 'institution', 'field', 'city']
    list_editable = ['status', 'is_published']
