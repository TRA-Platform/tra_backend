from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import BaseCommand


class Command(BaseCommand):

    def handle(self, *args, **options):
        for user in settings.ADMINS:
            username = user[0].replace(' ', '')
            email = user[1]
            user = User.objects.filter(email=email)
            if user.exists():
                print(f'Account {username} - {email} already exists')
                continue
            print('Creating account for %s (%s)' % (username, email))
            admin = User.objects.create_superuser(email=email, username=username,
                                                  password=settings.DEFAULT_ADMIN_PASSWORD)
            admin.is_active = True
            admin.is_admin = True
            admin.save()
