from django.contrib import admin
from .models import *

class RequirementInline(admin.TabularInline):
    model = Requirement
    extra = 0
    fields = ('title', 'category', 'priority', 'ai_generated')
    readonly_fields = ('ai_generated',)

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'owner')
    search_fields = ('name', 'description')
    raw_id_fields = ('owner', 'template')
    inlines = [RequirementInline]
    actions = ['archive_projects']

    def archive_projects(self, request, queryset):
        queryset.update(status=Project.ARCHIVED)
    archive_projects.short_description = "Archive selected projects"

@admin.register(RequirementCategory)
class RequirementCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_custom')
    list_filter = ('is_custom',)
    search_fields = ('name',)

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ('author', 'created_at')

class ChangeLogInline(admin.TabularInline):
    model = RequirementChangeLog
    extra = 0
    readonly_fields = ('user', 'changed_at')

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'category', 'priority', 'ai_generated')
    list_filter = ('project', 'category', 'priority', 'ai_generated')
    search_fields = ('title', 'description')
    raw_id_fields = ('project',)
    inlines = [CommentInline, ChangeLogInline]
    readonly_fields = ('version', 'created_at')

@admin.register(SrsTemplate)
class SrsTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'owner', 'created_at')
    list_filter = ('is_default', 'owner')
    search_fields = ('name', 'content')
    raw_id_fields = ('owner',)

@admin.register(ProjectMockup)
class ProjectMockupAdmin(admin.ModelAdmin):
    list_display = ('project', 'generated_at', 'modified_at')
    raw_id_fields = ('project',)
    readonly_fields = ('html_content',)

class WorkerTaskAdmin(admin.ModelAdmin):
    list_display = ('task_type', 'status', 'project', 'created_at', 'completed_at')
    list_filter = ('task_type', 'status', 'project')
    search_fields = ('project__name', 'error')
    readonly_fields = ('created_at', 'started_at', 'completed_at')
    list_editable = ('status',)
    actions = ['retry_tasks']
    date_hierarchy = 'created_at'

    def retry_tasks(self, request, queryset):
        for task in queryset.filter(status=WorkerTask.FAILURE):
            if task.task_type == WorkerTask.GENERATE_REQ:
                generate_requirement_task.delay(task.project_id, task.requirement.category_id)
            elif task.task_type == WorkerTask.GENERATE_MOCKUP:
                generate_mockup_task.delay(task.project_id)
            elif task.task_type == WorkerTask.PROCESS_SRS:
                process_srs_template_task.delay(task.project_id)
            task.status = WorkerTask.PENDING
            task.save()
    retry_tasks.short_description = "Retry selected failed tasks"

admin.site.register(Project, ProjectAdmin)
admin.site.register(WorkerTask, WorkerTaskAdmin)