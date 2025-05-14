from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Requirement, UserStory, Mockup, STATUS_ACTIVE, GENERATION_STATUS_COMPLETED
from .image_utils import render_html_to_png
from .s3_utils import upload_to_s3, generate_export_filename
from django.conf import settings
import io


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

@receiver(post_save, sender=Mockup)
def handle_mockup_image_upload(sender, instance, created, **kwargs):
    if not instance.html_content or instance.generation_status != GENERATION_STATUS_COMPLETED:
        return
    if instance.image and not instance.image.startswith("https://placehold.co") and instance.image != "":
        return
    try:
        png_data = render_html_to_png(instance.html_content)
        filename = generate_export_filename(
            instance.project.name,
            str(instance.id),
            file_extension='png'
        )
        url = upload_to_s3(png_data, filename, settings.S3_BUCKET_NAME, file_extension='png')
        Mockup.objects.filter(pk=instance.pk).update(image=url)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to upload mockup image to S3: {e}")

