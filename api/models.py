import uuid
from django.db import models
from django.contrib.auth.models import User

STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUS_COMPLETED = "completed"

STATUS_CHOICES = [
    (STATUS_DRAFT, "Draft"),
    (STATUS_ACTIVE, "Active"),
    (STATUS_ARCHIVED, "Archived"),
    (STATUS_COMPLETED, "Completed"),
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


class SrsTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    template_content = models.TextField(blank=True)
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
    operating_system = models.CharField(max_length=100, blank=True)
    priority_modules = models.TextField(blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    preliminary_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

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
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(
        max_length=50, choices=REQUIREMENT_CATEGORY_CHOICES, default=REQUIREMENT_CATEGORY_FUNCTIONAL,
    )
    version_number = models.IntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[v{self.version_number}] {self.title} (Project: {self.project.name})"


class RequirementHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name='history')
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50)
    version_number = models.IntegerField()
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    def __str__(self):
        return f"History v{self.version_number} for {self.requirement.title}"


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


class Mockup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='mockups')
    requirement = models.ForeignKey(
        Requirement, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mockups'
    )
    name = models.CharField(max_length=200)
    html_content = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Mockup {self.name} (Project: {self.project.name})"


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
