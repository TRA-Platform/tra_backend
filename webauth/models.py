import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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
