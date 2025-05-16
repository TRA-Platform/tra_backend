import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class ProjectRole(models.Model):
    ROLE_CHOICES = (
        ('OWNER', 'Owner'),
        ('ADMIN', 'Admin'),
        ('MANAGER', 'Manager'),
        ('MEMBER', 'Member'),
        ('VIEWER', 'Viewer'),
    )

    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_roles')
    project = models.ForeignKey('api.Project', on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='VIEWER')
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'project')

    def __str__(self):
        return f"{self.user.username} - {self.project.name} - {self.role}"


class AdminMember(models.Model):
    ROLE_ID = 9

    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    user = models.OneToOneField(to=User, on_delete=models.CASCADE, related_name='admin')
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Admin {self.user.username}"


class ManagerMember(models.Model):
    ROLE_ID = 2

    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    user = models.OneToOneField(to=User, on_delete=models.CASCADE, related_name='manager')
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Manager {self.user.username}"


class ModeratorMember(models.Model):
    ROLE_ID = 3

    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    user = models.OneToOneField(to=User, on_delete=models.CASCADE, related_name='moderator')
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Moderator {self.user.username}"
