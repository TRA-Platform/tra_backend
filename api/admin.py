# admin.py
from django.contrib import admin
from django.contrib import messages
from .models import (
    SrsTemplate, Project, Requirement, RequirementHistory,
    RequirementComment, DevelopmentPlan, DevelopmentPlanVersion, Mockup, SrsExport, SRS_FORMAT_PDF
)
from .tasks import (
    generate_requirements_task, export_srs_task,
    generate_development_plan_task, generate_mockups_task
)


@admin.action(description="Generate Requirements via GPT")
def admin_generate_requirements(modeladmin, request, queryset):
    for project in queryset:
        generate_requirements_task.delay(str(project.id))
        modeladmin.message_user(request, f"Started requirement generation for project '{project.name}'")


@admin.action(description="Export SRS (PDF)")
def admin_export_srs(modeladmin, request, queryset):
    user_request = request.user
    for project in queryset:
        export_srs_task.delay(
            str(project.id),
            created_by=user_request.id,
            fmt=SRS_FORMAT_PDF,
        )
        modeladmin.message_user(request, f"Started SRS export for project '{project.name}' as PDF")


@admin.action(description="Generate Development Plan via GPT")
def admin_generate_plan(modeladmin, request, queryset):
    for project in queryset:
        generate_development_plan_task.delay(str(project.id))
        modeladmin.message_user(request, f"Started dev plan generation for project '{project.name}'")


@admin.action(description="Generate Mockups (HTML) for each Requirement")
def admin_generate_mockups(modeladmin, request, queryset):
    for project in queryset:
        generate_mockups_task.delay(str(project.id))
        modeladmin.message_user(request, f"Started mockup generation for project '{project.name}'")


@admin.register(SrsTemplate)
class SrsTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at")
    search_fields = ("name",)
    list_filter = ("status", "created_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "status", "created_at")
    search_fields = ("name",)
    list_filter = ("status", "created_at")
    actions = [admin_generate_requirements, admin_export_srs, admin_generate_plan, admin_generate_mockups]


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "category", "status", "version_number", "created_at")
    list_filter = ("category", "status", "created_at")
    search_fields = ("title", "description")


@admin.register(RequirementHistory)
class RequirementHistoryAdmin(admin.ModelAdmin):
    list_display = ("requirement", "version_number", "changed_by", "changed_at", "status")
    list_filter = ("status", "changed_at", "version_number")
    search_fields = ("title", "description")


@admin.register(RequirementComment)
class RequirementCommentAdmin(admin.ModelAdmin):
    list_display = ("requirement", "user", "responsible_user", "created_at", "status")
    list_filter = ("status", "created_at")
    search_fields = ("text",)


@admin.register(DevelopmentPlan)
class DevelopmentPlanAdmin(admin.ModelAdmin):
    list_display = ("project", "current_version_number", "status", "created_at")
    list_filter = ("status", "created_at")


@admin.register(DevelopmentPlanVersion)
class DevelopmentPlanVersionAdmin(admin.ModelAdmin):
    list_display = ("plan", "version_number", "estimated_cost", "created_at", "status")
    list_filter = ("status", "created_at", "version_number")
    search_fields = ("notes",)


@admin.register(Mockup)
class MockupAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "requirement", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "html_content")


@admin.register(SrsExport)
class SrsExportAdmin(admin.ModelAdmin):
    list_display = ("project", "fmt", "status", "created_at")
    list_filter = ("status", "created_at", "project")
    search_fields = ("content", "fmt")
