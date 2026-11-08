"""作品页数据层测试：纯函数与模型定义；测试清单见 MEDIA_PLAN.md 第 12 节。"""

from datetime import datetime, timedelta, timezone as datetime_timezone
from types import SimpleNamespace

from django.apps import apps
from django.db import IntegrityError, models as django_models, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from userprofile.models import UserProfile
from .models import Media, MediaLikes, UserMedia
from .utils import (
    build_embed_url, build_external_url, decay, format_to_platform, MEDIA_HOT_DAILY_RETENTION,
    MediaFormat, MediaStatus, normalize_external_author_id, normalize_language, parse_media_url, real_hot,
)


class MediaUtilsTests(SimpleTestCase):
    def test_decay_factor(self):
        start = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
        self.assertAlmostEqual(decay(start, start), 1.0)
        self.assertAlmostEqual(decay(start, start + timedelta(days=1)), MEDIA_HOT_DAILY_RETENTION)
        self.assertAlmostEqual(decay(start, start + timedelta(days=6)), MEDIA_HOT_DAILY_RETENTION ** 6)
        self.assertGreater(decay(start, start - timedelta(days=1)), 1.0)

    def test_real_hot(self):
        start = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
        media = SimpleNamespace(hot_value=2.0, hot_value_updated_at=start)
        self.assertAlmostEqual(real_hot(media, start + timedelta(days=1)), 2.0 * MEDIA_HOT_DAILY_RETENTION)

    def test_parse_full_url(self):
        cases = [
            ('https://www.bilibili.com/video/BV1xx411c7mD/', MediaFormat.B_V, 'BV1xx411c7mD'),
            ('http://m.bilibili.com/video/BV1uv411q7Mv?p=1', MediaFormat.B_V, 'BV1uv411q7Mv'),
            ('https://bilibili.com/read/cv1646742/?from=search', MediaFormat.B_A, '1646742'),
            ('https://saolei.wang/bbs/9786', MediaFormat.C_P, '9786'),
        ]
        for url, expected_format, expected_suffix in cases:
            with self.subTest(url=url):
                self.assertEqual(parse_media_url(url), (expected_format, expected_suffix))

    def test_parse_rejects_invalid_url(self):
        invalid_urls = [
            'https://www.bilibili.com/opus/1266049845845557253',
            'https://b23.tv/BV1xx411c7mD',
            'https://www.bilibili.com.evil.com/video/BV1xx411c7mD',
            'http://www.saolei.wang/BBS/Title.asp?Id=9786',
            'http://saolei.wang/bbs/9786',
            'https://saolei.wang/other/9786',
            'https://www.bilibili.com/video/notabvid/',
            'https://www.bilibili.com/read/cvabc',
            'https://saolei.wang/bbs/abc',
            'https://user:pass@www.bilibili.com/video/BV1xx411c7mD',
            'javascript:alert(1)',
            '',
        ]
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_media_url(url)

    def test_parse_suffix(self):
        self.assertEqual(parse_media_url('BV1xx411c7mD'), (MediaFormat.B_V, 'BV1xx411c7mD'))
        self.assertEqual(parse_media_url('1646742', MediaFormat.B_A), (MediaFormat.B_A, '1646742'))
        self.assertEqual(parse_media_url('9786', MediaFormat.C_P), (MediaFormat.C_P, '9786'))
        with self.assertRaises(ValueError):
            parse_media_url('9786')
        with self.assertRaises(ValueError):
            parse_media_url('9786', 'B_o')

    def test_build_urls(self):
        self.assertEqual(build_external_url(MediaFormat.B_V, 'BV1xx411c7mD'), 'https://www.bilibili.com/video/BV1xx411c7mD/')
        self.assertEqual(build_external_url(MediaFormat.B_A, '1646742'), 'https://www.bilibili.com/read/cv1646742')
        self.assertEqual(build_external_url(MediaFormat.C_P, '9786'), 'https://saolei.wang/bbs/9786')
        self.assertIn('bvid=BV1xx411c7mD', build_embed_url(MediaFormat.B_V, 'BV1xx411c7mD'))
        self.assertIsNone(build_embed_url(MediaFormat.B_A, '1646742'))
        self.assertIsNone(build_embed_url(MediaFormat.C_P, '9786'))
        with self.assertRaises(ValueError):
            build_external_url('B_o', '1')

    def test_normalize_external_author_id(self):
        self.assertEqual(normalize_external_author_id(42), '42')
        self.assertEqual(normalize_external_author_id('  UCxxxxxxxxxxxxxxxxxxxxxx  '), 'UCxxxxxxxxxxxxxxxxxxxxxx')
        for invalid in (True, '', '   ', None, 1.5, 'x' * 129):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_external_author_id(invalid)

    def test_language_and_platform(self):
        self.assertEqual(normalize_language('  zh-cn  '), 'zh-cn')
        self.assertEqual(normalize_language(''), '')
        self.assertEqual(normalize_language('unknown-language'), 'unknown-language')
        with self.assertRaises(ValueError):
            normalize_language('x' * 33)
        self.assertEqual(format_to_platform(MediaFormat.B_V), 'B')
        self.assertEqual(format_to_platform(MediaFormat.B_A), 'B')
        self.assertEqual(format_to_platform(MediaFormat.C_P), 'c')
        with self.assertRaises(ValueError):
            format_to_platform('B_o')


class MediaModelDefinitionTests(SimpleTestCase):
    def test_language_is_free_text(self):
        field = Media._meta.get_field('language')
        self.assertIsInstance(field, django_models.CharField)
        self.assertEqual(field.max_length, 32)
        self.assertTrue(field.blank)
        self.assertEqual(field.choices or [], [])

    def test_format_and_status_choices(self):
        formats = [value for value, _ in Media._meta.get_field('format').choices]
        self.assertEqual(formats, [MediaFormat.B_V, MediaFormat.B_A, MediaFormat.C_P])
        statuses = [value for value, _ in Media._meta.get_field('status').choices]
        self.assertEqual(statuses, [MediaStatus.PENDING, MediaStatus.VERIFIED, MediaStatus.REJECTED])

    def test_status_replaces_legacy_deletion_fields(self):
        field_names = {field.name for field in Media._meta.get_fields()}
        self.assertIn('status', field_names)
        self.assertNotIn('verified', field_names)
        self.assertNotIn('deleted_at', field_names)
        self.assertNotIn('external_author_id', field_names)
        with self.assertRaises(LookupError):
            apps.get_model('media', 'MediaDeletionLog')

    def test_indexes_and_constraints(self):
        indexes = {index.name: list(index.fields) for index in Media._meta.indexes}
        self.assertEqual(indexes['media_pending_idx'], ['status', '-submitted_at'])
        self.assertEqual(indexes['media_user_hot_idx'], ['user', '-hot_value'])
        self.assertEqual(indexes['media_user_likes_idx'], ['user', '-likes'])
        self.assertEqual(indexes['media_user_created_idx'], ['user', '-created_at'])
        self.assertEqual(indexes['media_title_idx'], ['title'])
        self.assertEqual(indexes['media_latest_idx'], ['status', '-created_at', '-id'])
        media_constraints = {constraint.name: list(constraint.fields) for constraint in Media._meta.constraints}
        self.assertEqual(media_constraints['media_format_suffix_unique'], ['format', 'suffix'])
        likes_constraints = {constraint.name: list(constraint.fields) for constraint in MediaLikes._meta.constraints}
        self.assertEqual(likes_constraints['media_likes_user_media_unique'], ['user', 'media'])

    def test_user_media_primary_key(self):
        self.assertTrue(UserMedia._meta.get_field('user').primary_key)


class MediaModelPersistenceTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='media-data-layer', password='test-password')

    def _create_media(self, suffix='BV1xx411c7mD'):
        return Media.objects.create(
            user=self.user, title='test title', language='', created_at=timezone.now(),
            format=MediaFormat.B_V, suffix=suffix,
        )

    def test_unique_format_suffix(self):
        self._create_media()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._create_media()

    def test_rejected_media_still_blocks_resubmission(self):
        media = self._create_media()
        media.status = MediaStatus.REJECTED
        media.save(update_fields=['status'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._create_media()

    def test_status_defaults(self):
        media = self._create_media()
        self.assertEqual(media.status, MediaStatus.PENDING)
        self.assertIsNone(media.rejected_at)
        self.assertIsNone(media.rejected_by_id)
        self.assertEqual(media.reject_reason, '')
        self.assertEqual(media.refunded_likes, 0)

    def test_rejection_audit_fields_persist(self):
        media = self._create_media()
        media.status = MediaStatus.REJECTED
        media.rejected_at = timezone.now()
        media.rejected_by = self.user
        media.reject_reason = 'not minesweeper related'
        media.refunded_likes = 7
        media.save(update_fields=['status', 'rejected_at', 'rejected_by', 'reject_reason', 'refunded_likes'])
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.REJECTED)
        self.assertEqual(media.rejected_by_id, self.user.pk)
        self.assertEqual(media.reject_reason, 'not minesweeper related')
        self.assertEqual(media.refunded_likes, 7)

    def test_like_record_unique(self):
        media = self._create_media()
        MediaLikes.objects.create(user=self.user, media=media, likes=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MediaLikes.objects.create(user=self.user, media=media, likes=2)

    def test_user_media_defaults(self):
        profile = UserMedia.objects.create(user=self.user)
        self.assertEqual(profile.pk, self.user.pk)
        self.assertEqual(profile.likes_sent, 0)
        self.assertFalse(profile.banned)
