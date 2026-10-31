import logging
import uuid

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from msuser.models import UserMS
from userprofile.models import UserProfile
from userprofile.services import clean_user_name
from utils.exceptions import ExceptionToResponse
from utils.ranking_lock import ranking_access

logger = logging.getLogger('userprofile')


class Command(BaseCommand):
    help = 'Create a memorial account using two explicitly selected vacant IDs. Verify deletion and cleanup on the server first.'
    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=int)
        parser.add_argument('userms_id', type=int)
        parser.add_argument('username')
        for field in ('realname', 'firstname', 'lastname', 'country', 'signature'):
            parser.add_argument(f'--{field}', default='')

    @ranking_access(operation='memorial.create')
    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                for model, field in ((UserProfile, 'user_id'), (UserMS, 'userms_id')):
                    value = options[field]
                    maximum = model.objects.select_for_update().order_by('-pk').values_list('pk', flat=True).first()
                    if maximum is None or not 0 < value < maximum or model.objects.filter(pk=value).exists():
                        raise CommandError(f'{field} must be an unused positive ID below the current maximum ({maximum}).')
                user = UserProfile(
                    pk=options['user_id'], username=options['username'], country=options['country'], signature=options['signature'],
                    email=f"memorial-{options['user_id']}-{uuid.uuid4().hex}@accounts.invalid",
                    is_memorial=True, is_active=False,
                )
                for field in ('realname', 'firstname', 'lastname'):
                    setattr(user, field, clean_user_name(user, field, options[field]))
                user.set_unusable_password()
                user.userms = UserMS.objects.create(pk=options['userms_id'])
                user.full_clean()
                user.save(force_insert=True)  # noqa: DJM100 - only INSERT into the explicitly selected vacant ID
        except (ValidationError, IntegrityError, ExceptionToResponse) as error:
            raise CommandError(str(error)) from error
        logger.warning('Created memorial account user=%s userms=%s username=%s', user.pk, user.userms_id, user.username)
        self.stdout.write(self.style.SUCCESS(f'Created memorial account UserProfile #{user.pk}, UserMS #{user.userms_id}.'))
