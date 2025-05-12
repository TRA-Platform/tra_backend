from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Requirement, UserStory, Mockup, STATUS_ACTIVE


@receiver(post_save, sender=Requirement)
def handle_requirement_change(sender, instance, **kwargs):
    if instance.pk:
        Mockup.objects.filter(
            requirement=instance,
            status=STATUS_ACTIVE
        ).update(
            needs_regeneration=True,
            last_associated_change=timezone.now()
        )

@receiver(post_save, sender=UserStory)
def handle_user_story_change(sender, instance, **kwargs):
    if instance.pk:
        Mockup.objects.filter(
            user_story=instance,
            status=STATUS_ACTIVE
        ).update(
            needs_regeneration=True,
            last_associated_change=timezone.now()
        ) 