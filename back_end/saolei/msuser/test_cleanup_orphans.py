from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.db.models import QuerySet
from django.test import TestCase

from identifier.models import Identifier
from userprofile.models import UserProfile
from .models import UserMS


class CleanupOrphanUserMSTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(
            pk=42, username='retained', email='retained@example.com', userms=UserMS.objects.create(pk=302),
        )
        self.inactive = UserProfile.objects.create_user(
            pk=43, username='inactive', email='inactive@example.com', is_active=False, userms=UserMS.objects.create(pk=303),
        )
        self.orphan = UserMS.objects.create(pk=42)
        self.identifier = Identifier.objects.create(identifier='orphan identifier', safe=True, userms=self.orphan)

    def cleanup(self, **options):
        output = StringIO()
        call_command('cleanup_orphan_userms', stdout=output, **options)
        return output.getvalue()

    def test_dry_run_keeps_all_rows(self):
        self.assertIn('Would delete 1 orphan UserMS records', self.cleanup(dry_run=True))
        self.assertEqual(UserMS.objects.count(), 3)
        self.assertTrue(Identifier.objects.filter(pk=self.identifier.pk).exists())

    def test_cleanup_only_deletes_orphans_and_counts_userms_not_identifiers(self):
        UserMS.objects.create(pk=100)
        UserMS.objects.create(pk=101)
        self.assertIn('Deleted 3 orphan UserMS records', self.cleanup(batch_size=1))
        self.assertEqual(set(UserMS.objects.values_list('pk', flat=True)), {302, 303})
        self.assertTrue(UserProfile.objects.filter(pk=42, userms_id=302).exists())
        self.assertTrue(UserProfile.objects.filter(pk=43, userms_id=303, is_active=False).exists())
        self.assertFalse(Identifier.objects.filter(pk=self.identifier.pk).exists())
        self.assertIn('Deleted 0 orphan UserMS records', self.cleanup(batch_size=1))

    def test_invalid_batch_size_does_not_delete(self):
        for batch_size in (0, -1):
            with self.subTest(batch_size=batch_size), self.assertRaisesMessage(CommandError, '--batch-size must be positive'):
                self.cleanup(batch_size=batch_size)
        self.assertTrue(UserMS.objects.filter(pk=self.orphan.pk).exists())

    def test_rechecks_ownership_after_locking_candidates(self):
        select_for_update = QuerySet.select_for_update

        def link_before_lock(queryset, *args, **kwargs):
            UserProfile.objects.create_user(pk=55, username='newly-linked', email='newly-linked@example.com', userms=self.orphan)
            return select_for_update(queryset, *args, **kwargs)

        with patch.object(QuerySet, 'select_for_update', autospec=True, side_effect=link_before_lock):
            self.assertIn('Deleted 0 orphan UserMS records', self.cleanup())
        self.assertTrue(UserProfile.objects.filter(pk=55, userms_id=self.orphan.pk).exists())
        self.assertTrue(Identifier.objects.filter(pk=self.identifier.pk).exists())
