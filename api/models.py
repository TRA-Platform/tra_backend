import uuid
from django.db import models
from django.contrib.auth.models import User

STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUS_COMPLETED = "completed"

STATUS_CHOICES = [
    (STATUS_ACTIVE, "Active"),
    (STATUS_DRAFT, "Draft"),
    (STATUS_COMPLETED, "Completed"),
    (STATUS_ARCHIVED, "Archived"),
]

PROJECT_TYPE_WEBSITE = "website"
PROJECT_TYPE_MOBILE = "mobile"
PROJECT_TYPE_DESKTOP = "desktop"
PROJECT_TYPE_API = "api"
PROJECT_TYPE_OTHER = "other"

PROJECT_TYPE_CHOICES = [
    (PROJECT_TYPE_WEBSITE, "Website"),
    (PROJECT_TYPE_MOBILE, "Mobile App"),
    (PROJECT_TYPE_DESKTOP, "Desktop App"),
    (PROJECT_TYPE_API, "API Service"),
    (PROJECT_TYPE_OTHER, "Other"),
]

REQUIREMENT_CATEGORY_FUNCTIONAL = "functional"
REQUIREMENT_CATEGORY_NONFUNCTIONAL = "nonfunctional"
REQUIREMENT_CATEGORY_UIUX = "uiux"
REQUIREMENT_CATEGORY_OTHER = "other"

REQUIREMENT_CATEGORY_CHOICES = [
    ("functional", "Functional"),
    ("nonfunctional", "Non-functional"),
    ("uiux", "UI/UX"),
    ("other", "Other"),
]

REQUIREMENT_TYPE_FEATURE = "feature"
REQUIREMENT_TYPE_CONSTRAINT = "constraint"
REQUIREMENT_TYPE_QUALITY = "quality"
REQUIREMENT_TYPE_INTERFACE = "interface"
REQUIREMENT_TYPE_SECURITY = "security"
REQUIREMENT_TYPE_PERFORMANCE = "performance"
REQUIREMENT_TYPE_OTHER = "other"

REQUIREMENT_TYPE_CHOICES = [
    (REQUIREMENT_TYPE_FEATURE, "Feature"),
    (REQUIREMENT_TYPE_CONSTRAINT, "Constraint"),
    (REQUIREMENT_TYPE_QUALITY, "Quality"),
    (REQUIREMENT_TYPE_INTERFACE, "Interface"),
    (REQUIREMENT_TYPE_SECURITY, "Security"),
    (REQUIREMENT_TYPE_PERFORMANCE, "Performance"),
    (REQUIREMENT_TYPE_OTHER, "Other"),
]

SRS_FORMAT_PDF = "pdf"
SRS_FORMAT_DOCX = "docx"
SRS_FORMAT_HTML = "html"
SR_FORMAT_MARKDOWN = "md"

SRS_FORMAT_CHOICES = [
    (SRS_FORMAT_PDF, "PDF"),
    (SRS_FORMAT_DOCX, "DOCX"),
    (SRS_FORMAT_HTML, "HTML"),
    (SR_FORMAT_MARKDOWN, "Markdown"),
]

LANGUAGE_ENGLISH = "en"
LANGUAGE_RUSSIAN = "ru"
LANGUAGE_GERMAN = "de"

LANGUAGE_CHOICES = [
    (LANGUAGE_ENGLISH, "English"),
    (LANGUAGE_RUSSIAN, "Russian"),
    (LANGUAGE_GERMAN, "German"),
]

TEMPLATE_TYPE_DEFAULT = "default"
TEMPLATE_TYPE_CUSTOM = "custom"
TEMPLATE_TYPE_REGULATORY = "regulatory"
TEMPLATE_TYPE_INDUSTRY = "industry"

TEMPLATE_TYPE_CHOICES = [
    (TEMPLATE_TYPE_DEFAULT, "Default"),
    (TEMPLATE_TYPE_CUSTOM, "Custom"),
    (TEMPLATE_TYPE_REGULATORY, "Regulatory"),
    (TEMPLATE_TYPE_INDUSTRY, "Industry Standard"),
]

GENERATION_STATUS_PENDING = "pending"
GENERATION_STATUS_IN_PROGRESS = "in_progress"
GENERATION_STATUS_COMPLETED = "completed"
GENERATION_STATUS_FAILED = "failed"

GENERATION_STATUS_CHOICES = [
    (GENERATION_STATUS_PENDING, "Pending"),
    (GENERATION_STATUS_IN_PROGRESS, "In Progress"),
    (GENERATION_STATUS_COMPLETED, "Completed"),
    (GENERATION_STATUS_FAILED, "Failed"),
]


class SrsTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    template_content = models.TextField(blank=True)
    template_type = models.CharField(
        max_length=20, choices=TEMPLATE_TYPE_CHOICES, default=TEMPLATE_TYPE_DEFAULT
    )
    tags = models.JSONField(default=list, blank=True)
    preview_image = models.TextField(blank=True)  # Base64 encoded image or URL
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=200)
    short_description = models.TextField(blank=True)
    srs_template = models.ForeignKey(SrsTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    type_of_application = models.CharField(
        max_length=50, choices=PROJECT_TYPE_CHOICES, default=PROJECT_TYPE_WEBSITE,
    )
    color_scheme = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=50, blank=True, default=LANGUAGE_ENGLISH, choices=LANGUAGE_CHOICES)
    application_description = models.TextField(blank=True)
    target_users = models.TextField(blank=True)
    additional_requirements = models.TextField(blank=True)
    non_functional_requirements = models.TextField(blank=True)
    technology_stack = models.TextField(blank=True)
    operating_systems = models.JSONField(default=list, blank=True)  # List of operating systems
    priority_modules = models.TextField(blank=True)
    deadline_start = models.DateTimeField(null=True, blank=True)
    deadline_end = models.DateTimeField(null=True, blank=True)
    preliminary_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    scope = models.TextField(blank=True)

    # Generation status tracking
    generation_status = models.CharField(
        max_length=20, choices=GENERATION_STATUS_CHOICES, default=GENERATION_STATUS_PENDING
    )
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generation_completed_at = models.DateTimeField(null=True, blank=True)
    generation_error = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Requirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='requirements')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(
        max_length=50, choices=REQUIREMENT_CATEGORY_CHOICES, default=REQUIREMENT_CATEGORY_FUNCTIONAL,
    )
    requirement_type = models.CharField(
        max_length=50, choices=REQUIREMENT_TYPE_CHOICES, default=REQUIREMENT_TYPE_FEATURE,
    )
    version_number = models.IntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[v{self.version_number}] {self.title} (Project: {self.project.name})"

    class Meta:
        verbose_name_plural = "Requirements"
        ordering = ["status", "-created_at"]


class RequirementHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name='history')
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50)
    requirement_type = models.CharField(max_length=50)
    version_number = models.IntegerField()
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    def __str__(self):
        return f"History v{self.version_number} for {self.requirement.title}"


class UserStory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name='user_stories')
    role = models.CharField(max_length=100)  # "As a [role]"
    action = models.TextField()  # "I want to [action]"
    benefit = models.TextField()  # "So that [benefit]"
    acceptance_criteria = models.JSONField(default=list, blank=True)  # List of acceptance criteria
    version_number = models.IntegerField(default=1)

    # Generation status
    generation_status = models.CharField(
        max_length=20, choices=GENERATION_STATUS_CHOICES, default=GENERATION_STATUS_PENDING
    )
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generation_completed_at = models.DateTimeField(null=True, blank=True)
    generation_error = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"As a {self.role}, I want to {self.action}"

    class Meta:
        verbose_name_plural = "User Stories"
        ordering = ["status", "-created_at"]


class UserStoryHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_story = models.ForeignKey(UserStory, on_delete=models.CASCADE, related_name='history')
    role = models.CharField(max_length=100)
    action = models.TextField()
    benefit = models.TextField()
    acceptance_criteria = models.JSONField(default=list, blank=True)
    version_number = models.IntegerField()
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    def __str__(self):
        return f"History v{self.version_number} for User Story {self.user_story.id}"


class UserStoryComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_story = models.ForeignKey(UserStory, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )

    def __str__(self):
        return f"Comment by {self.user.username} on User Story {self.user_story.id}"


class RequirementComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    responsible_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_comments'
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )

    def __str__(self):
        return f"Comment by {self.user.username} on {self.requirement.title}"


class DevelopmentPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='development_plan')
    current_version_number = models.IntegerField(default=1)
    hourly_rates = models.JSONField(default=dict, blank=True)  # Dictionary of role:rate pairs

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DevelopmentPlanVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(DevelopmentPlan, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    roles_and_hours = models.TextField(blank=True)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT,
    )

    def __str__(self):
        return f"Plan v{self.version_number} for {self.plan.project.name}"


class UmlDiagram(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='uml_diagrams')
    plan_version = models.ForeignKey(DevelopmentPlanVersion, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='uml_diagrams')
    name = models.CharField(max_length=200)
    diagram_type = models.CharField(max_length=50)  # class, sequence, activity, etc.
    content = models.TextField()  # SVG or other format
    notes = models.TextField(blank=True)

    # Generation status
    generation_status = models.CharField(
        max_length=20, choices=GENERATION_STATUS_CHOICES, default=GENERATION_STATUS_PENDING
    )
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generation_completed_at = models.DateTimeField(null=True, blank=True)
    generation_error = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.diagram_type} Diagram: {self.name}"


class Mockup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='mockups')
    requirement = models.ForeignKey(
        Requirement, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mockups'
    )
    user_story = models.ForeignKey(
        UserStory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mockups'
    )
    name = models.CharField(max_length=200)
    html_content = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    version_number = models.IntegerField(default=1)

    # Generation status
    generation_status = models.CharField(
        max_length=20, choices=GENERATION_STATUS_CHOICES, default=GENERATION_STATUS_PENDING
    )
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generation_completed_at = models.DateTimeField(null=True, blank=True)
    generation_error = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Mockup {self.name} (Project: {self.project.name})"


class MockupHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mockup = models.ForeignKey(Mockup, on_delete=models.CASCADE, related_name='history')
    html_content = models.TextField(blank=True)
    version_number = models.IntegerField()
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    def __str__(self):
        return f"History v{self.version_number} for Mockup {self.mockup.name}"


class SrsExport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT,
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='exports')
    template = models.ForeignKey(SrsTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    fmt = models.CharField(max_length=10, default=SRS_FORMAT_PDF, choices=SRS_FORMAT_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Export for {self.project.name}"