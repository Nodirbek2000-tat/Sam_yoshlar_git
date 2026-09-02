from django.contrib import admin

from .models import BusinessProfile, Document, GalleryImage, Product


class ProductInline(admin.TabularInline):
    model = Product
    extra = 0


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'sphere', 'region', 'status', 'is_public']
    list_filter = ['sphere', 'status', 'region', 'is_public']
    search_fields = ['name', 'stir', 'user__email', 'user__full_name']
    list_editable = ['status']
    inlines = [ProductInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'price', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'business__name']


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'business', 'created_at']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'business', 'type', 'created_at']
    list_filter = ['type']
