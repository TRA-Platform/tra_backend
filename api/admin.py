from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    SrsTemplate, Project, Requirement, RequirementHistory, UserStory,
    UserStoryHistory, UserStoryComment, RequirementComment, DevelopmentPlan,
    DevelopmentPlanVersion, UmlDiagram, Mockup, MockupHistory, SrsExport,
    SRS_FORMAT_PDF, SRS_FORMAT_DOCX, SRS_FORMAT_HTML, SR_FORMAT_MARKDOWN
)
from .tasks import (
    generate_requirements_task, export_srs_task, generate_development_plan_task,
    generate_mockups_task, generate_user_stories_task, generate_uml_diagrams_task
)


class ReadOnlyInline(admin.TabularInline):
    can_delete = False
    extra = 0
    max_num = 0
    readonly_fields = []

    def get_readonly_fields(self, request, obj=None):
        return list(self.readonly_fields) or [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.action(description="Generate Requirements via GPT")
def admin_generate_requirements(modeladmin, request, queryset):
    for project in queryset:
        generate_requirements_task.delay(str(project.id))
        modeladmin.message_user(
            request,
            f"Started requirement generation for project '{project.name}'",
            messages.SUCCESS
        )


@admin.action(description="Generate User Stories via GPT")
def admin_generate_user_stories(modeladmin, request, queryset):
    count = 0
    for requirement in queryset:
        generate_user_stories_task.delay(str(requirement.id))
        count += 1

    modeladmin.message_user(
        request,
        f"Started user story generation for {count} requirements",
        messages.SUCCESS
    )


@admin.action(description="Export SRS as PDF")
def admin_export_srs_pdf(modeladmin, request, queryset):
    for project in queryset:
        export_srs_task.delay(
            str(project.id),
            created_by=request.user.id,
            fmt=SRS_FORMAT_PDF,
        )
        modeladmin.message_user(
            request,
            f"Started SRS export for project '{project.name}' as PDF",
            messages.SUCCESS
        )


@admin.action(description="Export SRS as DOCX")
def admin_export_srs_docx(modeladmin, request, queryset):
    for project in queryset:
        export_srs_task.delay(
            str(project.id),
            created_by=request.user.id,
            fmt=SRS_FORMAT_DOCX,
        )
        modeladmin.message_user(
            request,
            f"Started SRS export for project '{project.name}' as DOCX",
            messages.SUCCESS
        )


@admin.action(description="Export SRS as HTML")
def admin_export_srs_html(modeladmin, request, queryset):
    for project in queryset:
        export_srs_task.delay(
            str(project.id),
            created_by=request.user.id,
            fmt=SRS_FORMAT_HTML,
        )
        modeladmin.message_user(
            request,
            f"Started SRS export for project '{project.name}' as HTML",
            messages.SUCCESS
        )


@admin.action(description="Export SRS as Markdown")
def admin_export_srs_markdown(modeladmin, request, queryset):
    for project in queryset:
        export_srs_task.delay(
            str(project.id),
            created_by=request.user.id,
            fmt=SR_FORMAT_MARKDOWN,
        )
        modeladmin.message_user(
            request,
            f"Started SRS export for project '{project.name}' as Markdown",
            messages.SUCCESS
        )


@admin.action(description="Generate Development Plan via GPT")
def admin_generate_plan(modeladmin, request, queryset):
    for project in queryset:
        generate_development_plan_task.delay(str(project.id))
        modeladmin.message_user(
            request,
            f"Started dev plan generation for project '{project.name}'",
            messages.SUCCESS
        )


@admin.action(description="Generate Mockups (HTML) for Requirements")
def admin_generate_mockups(modeladmin, request, queryset):
    for project in queryset:
        generate_mockups_task.delay(str(project.id))
        modeladmin.message_user(
            request,
            f"Started mockup generation for project '{project.name}'",
            messages.SUCCESS
        )


@admin.action(description="Generate UML Diagrams")
def admin_generate_uml_diagrams(modeladmin, request, queryset):
    diagram_types = ["class", "sequence", "activity", "component"]
    for project in queryset:
        for diagram_type in diagram_types:
            generate_uml_diagrams_task.delay(str(project.id), diagram_type=diagram_type)
        modeladmin.message_user(
            request,
            f"Started UML diagram generation for project '{project.name}'",
            messages.SUCCESS
        )


class RequirementInline(admin.TabularInline):
    model = Requirement
    extra = 0
    fields = ('title', 'category', 'requirement_type', 'status', 'version_number')
    readonly_fields = ('version_number',)
    show_change_link = True


class RequirementHistoryInline(ReadOnlyInline):
    model = RequirementHistory
    fields = ('version_number', 'title', 'category', 'changed_by', 'changed_at', 'status')
    ordering = ('-version_number',)


class RequirementCommentInline(admin.TabularInline):
    model = RequirementComment
    extra = 0
    fields = ('user', 'text', 'responsible_user', 'created_at', 'status')
    readonly_fields = ('created_at',)


class UserStoryInline(admin.TabularInline):
    model = UserStory
    extra = 0
    fields = ('role', 'action', 'benefit', 'status', 'version_number')
    readonly_fields = ('version_number',)
    show_change_link = True


class UserStoryHistoryInline(ReadOnlyInline):
    model = UserStoryHistory
    fields = ('version_number', 'role', 'action', 'changed_by', 'changed_at', 'status')
    ordering = ('-version_number',)


class UserStoryCommentInline(admin.TabularInline):
    model = UserStoryComment
    extra = 0
    fields = ('user', 'text', 'created_at', 'status')
    readonly_fields = ('created_at',)


class DevelopmentPlanVersionInline(admin.TabularInline):
    model = DevelopmentPlanVersion
    extra = 0
    fields = ('version_number', 'estimated_cost', 'created_by', 'created_at', 'status')
    readonly_fields = ('created_at',)
    show_change_link = True


class UmlDiagramInline(admin.TabularInline):
    model = UmlDiagram
    extra = 0
    fields = ('name', 'diagram_type', 'generation_status', 'status')
    show_change_link = True


class MockupInline(admin.TabularInline):
    model = Mockup
    extra = 0
    fields = ('name', 'requirement', 'version_number', 'generation_status', 'status')
    readonly_fields = ('version_number',)
    show_change_link = True


class MockupHistoryInline(ReadOnlyInline):
    model = MockupHistory
    fields = ('version_number', 'changed_by', 'changed_at', 'status')
    ordering = ('-version_number',)


class SrsExportInline(admin.TabularInline):
    model = SrsExport
    extra = 0
    fields = ('fmt', 'created_by', 'created_at', 'status')
    readonly_fields = ('created_at',)
    show_change_link = True


@admin.register(SrsTemplate)
class SrsTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'template_type', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    save_on_top = True

    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'description', 'template_type', 'status')
        }),
        ('Content', {
            'fields': ('template_content', 'preview_image'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('tags', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'created_by', 'type_of_application',
        'generation_status', 'status', 'created_at'
    )
    list_filter = (
        'status', 'generation_status', 'type_of_application',
        'created_at', 'deadline_end'
    )
    search_fields = ('name', 'short_description', 'application_description')
    readonly_fields = (
        'created_at', 'updated_at', 'generation_started_at',
        'generation_completed_at'
    )
    actions = [
        admin_generate_requirements,
        admin_export_srs_pdf,
        admin_export_srs_docx,
        admin_export_srs_html,
        admin_export_srs_markdown,
        admin_generate_plan,
        admin_generate_mockups,
        admin_generate_uml_diagrams
    ]
    save_on_top = True

    inlines = [
        RequirementInline,
        UmlDiagramInline,
        MockupInline,
        SrsExportInline
    ]

    fieldsets = (
        ('Project Information', {
            'fields': (
                'name', 'short_description', 'created_by', 'srs_template',
                'type_of_application', 'status'
            )
        }),
        ('Details', {
            'fields': (
                'application_description', 'target_users',
                'additional_requirements', 'non_functional_requirements'
            ),
            'classes': ('collapse',),
        }),
        ('Technical Information', {
            'fields': (
                'technology_stack', 'operating_systems', 'priority_modules'
            ),
            'classes': ('collapse',),
        }),
        ('Styling', {
            'fields': ('color_scheme', 'language'),
            'classes': ('collapse',),
        }),
        ('Planning', {
            'fields': ('deadline_start', 'deadline_end', 'preliminary_budget', 'scope'),
            'classes': ('collapse',),
        }),
        ('Generation Status', {
            'fields': (
                'generation_status', 'generation_started_at',
                'generation_completed_at', 'generation_error'
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'project_link', 'category', 'requirement_type',
        'status', 'version_number', 'created_at'
    )
    list_filter = (
        'status', 'category', 'requirement_type',
        'created_at', 'updated_at'
    )
    search_fields = ('title', 'description', 'project__name')
    readonly_fields = ('created_at', 'updated_at', 'version_number')
    actions = [admin_generate_user_stories]
    save_on_top = True

    inlines = [
        UserStoryInline,
        RequirementCommentInline,
        RequirementHistoryInline
    ]

    fieldsets = (
        ('Requirement Information', {
            'fields': (
                'title', 'project', 'category', 'requirement_type',
                'status', 'version_number', 'parent'
            )
        }),
        ('Details', {
            'fields': ('description',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def project_link(self, obj):
        url = reverse("admin:api_project_change", args=[obj.project.id])
        return format_html('<a href="{}">{}</a>', url, obj.project.name)

    project_link.short_description = 'Project'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project')


@admin.register(RequirementHistory)
class RequirementHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'requirement_link', 'version_number',
        'title', 'changed_by', 'changed_at', 'status'
    )
    list_filter = ('status', 'changed_at', 'version_number')
    search_fields = ('title', 'description', 'requirement__title')
    readonly_fields = ('changed_at',)

    fieldsets = (
        ('History Information', {
            'fields': (
                'requirement', 'version_number', 'title',
                'changed_by', 'changed_at', 'status'
            )
        }),
        ('Details', {
            'fields': ('description', 'category', 'requirement_type'),
        }),
    )

    def requirement_link(self, obj):
        url = reverse("admin:api_requirement_change", args=[obj.requirement.id])
        return format_html('<a href="{}">{}</a>', url, obj.requirement.title)

    requirement_link.short_description = 'Requirement'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requirement', 'changed_by')


@admin.register(UserStory)
class UserStoryAdmin(admin.ModelAdmin):
    list_display = (
        'role_action_preview', 'requirement_link',
        'version_number', 'generation_status', 'status', 'created_at'
    )
    list_filter = (
        'status', 'generation_status', 'created_at',
        'updated_at', 'version_number'
    )
    search_fields = ('role', 'action', 'benefit', 'requirement__title')
    readonly_fields = (
        'created_at', 'updated_at', 'version_number',
        'generation_started_at', 'generation_completed_at'
    )
    save_on_top = True

    inlines = [UserStoryCommentInline, UserStoryHistoryInline]

    fieldsets = (
        ('User Story Information', {
            'fields': ('requirement', 'role', 'status', 'version_number')
        }),
        ('Details', {
            'fields': ('action', 'benefit', 'acceptance_criteria'),
        }),
        ('Generation Status', {
            'fields': (
                'generation_status', 'generation_started_at',
                'generation_completed_at', 'generation_error'
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def role_action_preview(self, obj):
        return f"As a {obj.role}, I want to {obj.action[:50]}..."

    role_action_preview.short_description = 'User Story'

    def requirement_link(self, obj):
        url = reverse("admin:api_requirement_change", args=[obj.requirement.id])
        return format_html('<a href="{}">{}</a>', url, obj.requirement.title)

    requirement_link.short_description = 'Requirement'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requirement')


@admin.register(UserStoryHistory)
class UserStoryHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'user_story_link', 'version_number',
        'role_action_preview', 'changed_by', 'changed_at', 'status'
    )
    list_filter = ('status', 'changed_at', 'version_number')
    search_fields = ('role', 'action', 'benefit', 'user_story__role')
    readonly_fields = ('changed_at',)

    fieldsets = (
        ('History Information', {
            'fields': (
                'user_story', 'version_number', 'changed_by',
                'changed_at', 'status'
            )
        }),
        ('Details', {
            'fields': ('role', 'action', 'benefit', 'acceptance_criteria'),
        }),
    )

    def role_action_preview(self, obj):
        return f"As a {obj.role}, I want to {obj.action[:50]}..."

    role_action_preview.short_description = 'Details'

    def user_story_link(self, obj):
        url = reverse("admin:api_userstory_change", args=[obj.user_story.id])
        return format_html('<a href="{}">{}</a>', url, f"User Story #{obj.user_story.id}")

    user_story_link.short_description = 'User Story'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user_story', 'changed_by')


@admin.register(UserStoryComment)
class UserStoryCommentAdmin(admin.ModelAdmin):
    list_display = ('user_story_link', 'user', 'text_preview', 'created_at', 'status')
    list_filter = ('status', 'created_at', 'user')
    search_fields = ('text', 'user__username', 'user_story__role', 'user_story__action')
    readonly_fields = ('created_at',)

    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

    text_preview.short_description = 'Comment'

    def user_story_link(self, obj):
        url = reverse("admin:api_userstory_change", args=[obj.user_story.id])
        return format_html('<a href="{}">{}</a>', url, f"User Story #{obj.user_story.id}")

    user_story_link.short_description = 'User Story'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user_story', 'user')


@admin.register(RequirementComment)
class RequirementCommentAdmin(admin.ModelAdmin):
    list_display = (
        'requirement_link', 'user', 'responsible_user',
        'text_preview', 'created_at', 'status'
    )
    list_filter = ('status', 'created_at', 'user', 'responsible_user')
    search_fields = ('text', 'user__username', 'requirement__title')
    readonly_fields = ('created_at',)

    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

    text_preview.short_description = 'Comment'

    def requirement_link(self, obj):
        url = reverse("admin:api_requirement_change", args=[obj.requirement.id])
        return format_html('<a href="{}">{}</a>', url, obj.requirement.title)

    requirement_link.short_description = 'Requirement'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requirement', 'user', 'responsible_user')


@admin.register(DevelopmentPlan)
class DevelopmentPlanAdmin(admin.ModelAdmin):
    list_display = ('project_link', 'current_version_number', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('project__name',)
    readonly_fields = ('created_at', 'updated_at')

    inlines = [DevelopmentPlanVersionInline]

    fieldsets = (
        ('Plan Information', {
            'fields': ('project', 'current_version_number', 'status')
        }),
        ('Details', {
            'fields': ('hourly_rates',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def project_link(self, obj):
        url = reverse("admin:api_project_change", args=[obj.project.id])
        return format_html('<a href="{}">{}</a>', url, obj.project.name)

    project_link.short_description = 'Project'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project')


@admin.register(DevelopmentPlanVersion)
class DevelopmentPlanVersionAdmin(admin.ModelAdmin):
    list_display = (
        'plan_project', 'version_number', 'estimated_cost',
        'created_by', 'created_at', 'status'
    )
    list_filter = ('status', 'created_at', 'version_number')
    search_fields = ('notes', 'plan__project__name')
    readonly_fields = ('created_at',)

    inlines = [UmlDiagramInline]

    fieldsets = (
        ('Version Information', {
            'fields': ('plan', 'version_number', 'created_by', 'created_at', 'status')
        }),
        ('Details', {
            'fields': ('roles_and_hours', 'estimated_cost', 'notes'),
        }),
    )

    def plan_project(self, obj):
        project_name = obj.plan.project.name
        url = reverse("admin:api_developmentplan_change", args=[obj.plan.id])
        return format_html('<a href="{}">{} (Plan)</a>', url, project_name)

    plan_project.short_description = 'Project'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('plan', 'plan__project', 'created_by')


@admin.register(UmlDiagram)
class UmlDiagramAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'project_link', 'diagram_type',
        'generation_status', 'status', 'created_at'
    )
    list_filter = ('status', 'diagram_type', 'generation_status', 'created_at')
    search_fields = ('name', 'notes', 'project__name')
    readonly_fields = (
        'created_at', 'updated_at', 'generation_started_at',
        'generation_completed_at'
    )

    fieldsets = (
        ('Diagram Information', {
            'fields': (
                'name', 'project', 'plan_version',
                'diagram_type', 'status'
            )
        }),
        ('Content', {
            'fields': ('content', 'notes'),
            'classes': ('monospace',),
        }),
        ('Generation Status', {
            'fields': (
                'generation_status', 'generation_started_at',
                'generation_completed_at', 'generation_error'
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def project_link(self, obj):
        url = reverse("admin:api_project_change", args=[obj.project.id])
        return format_html('<a href="{}">{}</a>', url, obj.project.name)

    project_link.short_description = 'Project'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project')

    class Media:
        css = {
            'all': ('admin/css/monospace.css',)
        }


@admin.register(Mockup)
class MockupAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'project_link', 'requirement_link',
        'version_number', 'generation_status', 'status', 'created_at'
    )
    list_filter = ('status', 'generation_status', 'created_at', 'version_number')
    search_fields = ('name', 'html_content', 'project__name')
    readonly_fields = (
        'created_at', 'updated_at', 'version_number',
        'generation_started_at', 'generation_completed_at'
    )

    inlines = [MockupHistoryInline]

    fieldsets = (
        ('Mockup Information', {
            'fields': (
                'name', 'project', 'requirement', 'user_story',
                'created_by', 'status', 'version_number'
            )
        }),
        ('Content', {
            'fields': ('html_content',),
            'classes': ('collapse',),
        }),
        ('Generation Status', {
            'fields': (
                'generation_status', 'generation_started_at',
                'generation_completed_at', 'generation_error'
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def project_link(self, obj):
        url = reverse("admin:api_project_change", args=[obj.project.id])
        return format_html('<a href="{}">{}</a>', url, obj.project.name)

    project_link.short_description = 'Project'

    def requirement_link(self, obj):
        if obj.requirement:
            url = reverse("admin:api_requirement_change", args=[obj.requirement.id])
            return format_html('<a href="{}">{}</a>', url, obj.requirement.title)
        return "—"

    requirement_link.short_description = 'Requirement'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'project', 'requirement', 'user_story', 'created_by'
        )


@admin.register(MockupHistory)
class MockupHistoryAdmin(admin.ModelAdmin):
    list_display = ('mockup_link', 'version_number', 'changed_by', 'changed_at', 'status')
    list_filter = ('status', 'changed_at', 'version_number')
    search_fields = ('mockup__name',)
    readonly_fields = ('changed_at',)

    fieldsets = (
        ('History Information', {
            'fields': (
                'mockup', 'version_number', 'changed_by',
                'changed_at', 'status'
            )
        }),
        ('Content', {
            'fields': ('html_content',),
            'classes': ('collapse',),
        }),
    )

    def mockup_link(self, obj):
        url = reverse("admin:api_mockup_change", args=[obj.mockup.id])
        return format_html('<a href="{}">{}</a>', url, obj.mockup.name)

    mockup_link.short_description = 'Mockup'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('mockup', 'changed_by')


@admin.register(SrsExport)
class SrsExportAdmin(admin.ModelAdmin):
    list_display = ('project', 'format_display', 'created_by', 'created_at', 'status')
    list_filter = ('status', 'fmt', 'created_at')
    search_fields = ('project__name',)
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Export Information', {
            'fields': ('project', 'template', 'fmt', 'created_by', 'status')
        }),
        ('Content', {
            'fields': ('content',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def format_display(self, obj):
        format_dict = dict([
            (SRS_FORMAT_PDF, "PDF"),
            (SRS_FORMAT_DOCX, "DOCX"),
            (SRS_FORMAT_HTML, "HTML"),
            (SR_FORMAT_MARKDOWN, "Markdown"),
        ])
        return format_dict.get(obj.fmt, obj.fmt)

    format_display.short_description = 'Format'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project', 'template', 'created_by')


class AdminConfig(admin.sites.AdminSite):
    site_header = 'Requirements Management System'
    site_title = 'Requirements Management'
    index_title = 'System Administration'

    class Media:
        css = {
            'all': ('admin/css/custom.css',)
        }
