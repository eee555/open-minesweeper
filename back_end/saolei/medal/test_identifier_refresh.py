from contextlib import ExitStack
from datetime import timedelta
import json
import random
from unittest.mock import patch

from django.tasks import TaskResultStatus
from django.test import override_settings
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from identifier.services import bind_identifier, unbind_identifier
from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .models import MedalGrant, PlayerProgress
from .services import evaluate_player, refresh_player_medals
from .tasks import task_refresh_player_medals
from .tests import MedalTestCase
from .utils import NOVICE_LEVELS, NOVICE_REVIEW

OFFICIAL, IDENTIFIER = MS_TextChoices.State.OFFICIAL, MS_TextChoices.State.IDENTIFIER
RANK_DEPENDENCIES = [
    'newest_cache.update_bulk', 'add_videos_to_speed_ranks', 'add_videos_to_custom_pluck_ranks', 'add_videos_to_eff_ranks',
    'remove_videos_from_speed_ranks', 'remove_videos_from_custom_pluck_ranks', 'remove_videos_from_eff_ranks',
]
RANDOM_LEVELS = {'b': (20000, 2500, 10, 40), 'i': (120000, 18000, 50, 120), 'e': (300000, 55000, 100, 250)}
RANDOM_MODES = [MS_TextChoices.Mode.STD] * 17 + [MS_TextChoices.Mode.JSW, MS_TextChoices.Mode.QWC, MS_TextChoices.Mode.RKC]


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class IdentifierMedalRefreshTests(MedalTestCase):
    def setUp(self):
        self.base = timezone.now() - timedelta(days=100)
        self.ids = iter(range(6_000_000, 7_000_000))

    def make_player(self, name):
        userms = UserMS.objects.create()
        user = UserProfile.objects.create_user(username=name, email=f'{name}@example.com', userms=userms)
        return user, userms

    def make_videos(self, user, rows):
        videos = []
        for identifier, level, mode, timems, bv, right_ce, left_ce, state in rows:
            expand = ExpandVideoModel.objects.create(identifier=identifier)
            videos.append(VideoModel(
                id=next(self.ids), player=user, video=expand, file='videos/identifier-medal.evf', software='e', level=level, mode=mode, state=state,
                timems=timems, bv=bv, left=left_ce + 5, right=right_ce + 2, double=0, left_ce=left_ce, right_ce=right_ce, double_ce=0,
            ))
        return VideoModel.objects.bulk_create(videos)

    def make_video(self, user, identifier, *, level='b', timems=10000, days=0, state=IDENTIFIER):
        video = self.make_videos(user, [(identifier, level, MS_TextChoices.Mode.STD, timems, 10, 0, 10, state)])[0]
        VideoModel.objects.filter(pk=video.pk).update(upload_time=self.base + timedelta(days=days))
        return VideoModel.objects.get(pk=video.pk)

    def run_identifier(self, operation, identifier, userms):
        with ExitStack() as stack:
            for dependency in RANK_DEPENDENCIES:
                stack.enter_context(patch(f'identifier.services.{dependency}'))
            with self.captureOnCommitCallbacks(execute=True):
                operation(identifier, userms)
        row = DBTaskResult.objects.get(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY)
        self.assertIn('video_ids', row.args_kwargs['kwargs'])
        with self.captureOnCommitCallbacks(execute=True):
            task_refresh_player_medals.call(*row.args_kwargs['args'], **row.args_kwargs['kwargs'])
        row.delete()
        return row.args_kwargs['kwargs']

    def snapshot(self, user):
        grants = sorted(
            (row.definition_code, row.scope_key, row.stage, row.video_id, row.granted_at, json.dumps(row.evidence, sort_keys=True, default=str),
             tuple((entry.get('stage'), entry.get('evidence_id'), entry.get('at')) for entry in row.stage_log or []))
            for row in MedalGrant.objects.filter(user=user, revoked_at__isnull=True)
        )
        progress = sorted((row.code, row.current_stage, row.current_value, json.dumps(row.extra, sort_keys=True, default=str)) for row in PlayerProgress.objects.filter(user=user))
        return grants, progress

    def assert_matches_full_evaluation(self, user, label=''):
        incremental = self.snapshot(user)
        with self.captureOnCommitCallbacks(execute=True):
            evaluate_player(user.id)
        self.assertEqual(incremental, self.snapshot(user), label)

    def active(self, user, code):
        return MedalGrant.objects.filter(user=user, definition_code=code, revoked_at__isnull=True).first()

    def test_bind_and_unbind_update_medals_through_queued_incremental_refresh(self):
        user, userms = self.make_player('identifier_medal')
        identifier = Identifier.objects.create(identifier='medal-new', safe=True)
        old = self.make_video(user, 'medal-old', timems=9000, days=50, state=OFFICIAL)
        same_stage_earlier = self.make_video(user, 'medal-new', timems=8000, days=10)
        self.make_video(user, 'medal-new', level='i', timems=60000, days=20)
        completing = self.make_video(user, 'medal-new', level='e', timems=200000, days=30)
        faster = self.make_video(user, 'medal-new', timems=4500, days=60)
        with self.captureOnCommitCallbacks(execute=True):
            evaluate_player(user.id)
        self.assertEqual((self.active(user, 'ability.time.b').stage, self.active(user, 'ability.time.b').video_id), (10000, old.id))
        self.assertIsNone(self.active(user, NOVICE_LEVELS))

        kwargs = self.run_identifier(bind_identifier, identifier, userms)
        self.assertNotIn('full', kwargs)
        self.assertNotIn('invalidate_once', kwargs)
        grant = self.active(user, 'ability.time.b')
        self.assertEqual((grant.stage, grant.video_id), (5000, faster.id))
        self.assertEqual(grant.granted_at, same_stage_earlier.upload_time)
        self.assertEqual(self.active(user, NOVICE_LEVELS).video_id, completing.id)
        self.assertEqual(self.active(user, NOVICE_REVIEW).granted_at, same_stage_earlier.upload_time)
        self.assert_matches_full_evaluation(user)

        kwargs = self.run_identifier(unbind_identifier, identifier, userms)
        self.assertEqual((kwargs['degrade_levels'], kwargs['invalidate_once']), (['b', 'e', 'i'], True))
        grant = self.active(user, 'ability.time.b')
        self.assertEqual((grant.stage, grant.video_id, grant.granted_at), (10000, old.id, old.upload_time))
        self.assertIsNone(self.active(user, NOVICE_LEVELS))
        self.assertEqual(self.active(user, NOVICE_REVIEW).granted_at, old.upload_time)
        self.assert_matches_full_evaluation(user)

    def build_random_player(self, seed, pick, total=300, batches=5):
        rng = random.Random(seed)
        user, userms = self.make_player(f'identifier_random_{seed}')
        identifier = Identifier.objects.create(identifier=f'medal-random-{seed}', safe=True)
        per_batch = total // batches
        for batch in range(batches):
            rows = []
            for offset in range(per_batch):
                index = batch * per_batch + offset
                level = rng.choice('bie')
                slow, fast, bv_min, bv_max = RANDOM_LEVELS[level]
                timems = int(slow - (slow - fast) * index / total * rng.uniform(0.6, 1.0))
                bv = rng.randint(bv_min, bv_max)
                right_ce = 0 if rng.random() < 0.3 else rng.randint(5, bv // 2)
                left_ce = max(1, int(bv * rng.uniform(0.9, 1.3)) - right_ce)
                mode = rng.choice(RANDOM_MODES)
                tag = identifier.identifier if pick(index, level, mode) else 'medal-random-old'
                rows.append((tag, level, mode, timems, bv, right_ce, left_ce, OFFICIAL))
            ids = [video.id for video in self.make_videos(user, rows)]
            VideoModel.objects.filter(pk__in=ids).update(upload_time=self.base + timedelta(days=20 * batch))
            with self.captureOnCommitCallbacks(execute=True):
                if batch == 0:
                    evaluate_player(user.id)
                else:
                    refresh_player_medals(user.id, video_ids=ids)
        VideoModel.objects.filter(player=user, video__identifier=identifier.identifier).update(state=IDENTIFIER)
        with self.captureOnCommitCallbacks(execute=True):
            evaluate_player(user.id)
        return user, userms, identifier

    def test_random_batches_match_full_evaluation(self):
        scenarios = [
            ('every sixth video', lambda index, level, mode: index % 6 == 0),
            ('all expert videos', lambda index, level, mode: level == 'e'),
            ('all non-standard modes', lambda index, level, mode: mode != MS_TextChoices.Mode.STD),
            ('earliest videos', lambda index, level, mode: index < 30),
            ('latest videos', lambda index, level, mode: index >= 270),
        ]
        for seed, (label, pick) in enumerate(scenarios, start=1):
            with self.subTest(label):
                user, userms, identifier = self.build_random_player(seed, pick)
                before = self.snapshot(user)
                self.run_identifier(bind_identifier, identifier, userms)
                self.assertNotEqual(before, self.snapshot(user), label)
                self.assert_matches_full_evaluation(user, f'{label} bind')
                self.run_identifier(unbind_identifier, identifier, userms)
                self.assert_matches_full_evaluation(user, f'{label} unbind')
