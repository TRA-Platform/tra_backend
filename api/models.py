import logging

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)


class Project(models.Model):
    DRAFT = 'DRAFT'
    ACTIVE = 'ACTIVE'
    ARCHIVED = 'ARCHIVED'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (ACTIVE, 'Active'),
        (ARCHIVED, 'Archived'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    template = models.ForeignKey('SrsTemplate', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class RequirementCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_custom = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Requirement(models.Model):
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'
    PRIORITY_CHOICES = [
        (HIGH, 'High'),
        (MEDIUM, 'Medium'),
        (LOW, 'Low'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    category = models.ForeignKey(RequirementCategory, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=MEDIUM)
    ai_generated = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} v{self.version}"


class SrsTemplate(models.Model):
    name = models.CharField(max_length=150)
    content = models.TextField()
    is_default = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} {'(Default)' if self.is_default else ''}"


class ProjectMockup(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE)
    html_content = models.TextField()
    generated_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Mockup for {self.project.name}"


class RequirementChangeLog(models.Model):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    old_value = models.TextField()
    new_value = models.TextField()
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Change #{self.id} for {self.requirement.title}"


class Comment(models.Model):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment by {self.author} on {self.created_at}"


class WorkerTask(models.Model):
    GENERATE_REQ = 'GEN_REQ'
    GENERATE_MOCKUP = 'GEN_MOCK'
    PROCESS_SRS = 'PROC_SRS'
    TASK_TYPES = [
        (GENERATE_REQ, 'Requirement Generation'),
        (GENERATE_MOCKUP, 'Mockup Generation'),
        (PROCESS_SRS, 'SRS Processing'),
    ]

    PENDING = 'PENDING'
    STARTED = 'STARTED'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (STARTED, 'Started'),
        (SUCCESS, 'Success'),
        (FAILURE, 'Failure'),
    ]

    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True)
    requirement = models.ForeignKey(Requirement, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    result = models.JSONField(null=True)
    error = models.TextField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.get_status_display()}"
