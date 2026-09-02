from django.contrib import admin

from .models import Organization, Problem, Solution


class ProblemInline(admin.TabularInline):
    model = Problem
    extra = 0
    fields = ['category', 'description', 'status', 'is_published']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'sphere', 'contact_person', 'phone', 'created_at']
    list_filter = ['sphere', 'region']
    search_fields = ['name', 'contact_person', 'phone']
    inlines = [ProblemInline]


class SolutionInline(admin.StackedInline):
    model = Solution
    extra = 0
    fields = ['author_name', 'title', 'description', 'technologies', 'status']


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ['organization', 'category', 'status', 'solution_total', 'is_published',
                    'created_at']
    list_filter = ['category', 'status', 'is_published']
    search_fields = ['description', 'organization__name']
    list_editable = ['status', 'is_published']
    inlines = [SolutionInline]

    @admin.display(description="Yechimlar")
    def solution_total(self, obj):
        return obj.solutions_count


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ['title', 'author_name', 'problem', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['title', 'description', 'author_name']
    list_editable = ['status']
