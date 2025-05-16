from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.conf import settings

from api.models import Project
from webauth.models import ProjectRole

@receiver(post_save, sender=User)
def create_default_roles(sender, instance, created, **kwargs):
    if created and hasattr(settings, 'DEFAULT_USER_ROLES'):
        for role in settings.DEFAULT_USER_ROLES:
            if role == 'admin':
                from webauth.models import AdminMember
                AdminMember.objects.create(user=instance)
            elif role == 'manager':
                from webauth.models import ManagerMember
                ManagerMember.objects.create(user=instance)
            elif role == 'moderator':
                from webauth.models import ModeratorMember
                ModeratorMember.objects.create(user=instance)


@receiver(post_save, sender=Project)
def create_project_owner_role(sender, instance, created, **kwargs):
    if created:
        if not ProjectRole.objects.filter(user=instance.created_by, project=instance).exists():
            ProjectRole.objects.create(
                user=instance.created_by,
                project=instance,
                role='OWNER'
            ) 