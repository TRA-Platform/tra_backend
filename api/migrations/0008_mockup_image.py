# Generated by Django 4.2.2 on 2025-05-14 13:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_project_mockups_completed_project_mockups_total_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='mockup',
            name='image',
            field=models.URLField(default='https://placehold.co/1600x900/EEE/31343C'),
        ),
    ]
