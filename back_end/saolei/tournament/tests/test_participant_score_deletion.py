from unittest.mock import patch

from django.db import transaction

from tournament.models import GSCParticipant, TournamentParticipant, TournamentUser, WeeklyParticipant
from .base import cache, timedelta, timezone, Tournament_TextChoices, TOURNAMENT_USER_CACHE_KEYS, TournamentTestCaseBase


class ParticipantScoreDeletionTests(TournamentTestCaseBase):
    def setUp(self):
        super().setUp()
        self.last_updated = timezone.now()
        self.end_time = self.last_updated - timedelta(days=730)
        self.tournament.start_time = self.end_time - timedelta(days=1)
        self.tournament.end_time = self.end_time
        self.tournament.state = Tournament_TextChoices.State.AWARDED
        self.tournament.host = self.user
        self.tournament.save(update_fields=['start_time', 'end_time', 'state', 'host'])
        self.weekly = self.create_weekly_tournament(
            start_time=self.tournament.start_time, end_time=self.end_time,
            state=Tournament_TextChoices.State.AWARDED,
        )

    def seed_scores(self, *, current=175, total=500, gsc=250, weekly=250):
        record = TournamentUser.objects.get(user_id=self.user.id)
        record.score_current = current
        record.score_total = total
        record.gsc_total = gsc
        record.weekly_total = weekly
        record.weekly_classic_total = weekly
        record.last_updated = self.last_updated
        record.save(update_fields=['score_current', 'score_total', 'gsc_total', 'weekly_total', 'weekly_classic_total', 'last_updated'])
        self.tournament_cache.update_tournament_user(record)
        return record

    def test_child_and_parent_deletions_revoke_decayed_scores_once(self):
        for model, tournament, category in (
            (GSCParticipant, self.tournament, 'gsc'),
            (WeeklyParticipant, self.weekly, 'weekly'),
        ):
            for parent_delete in (False, True):
                with self.subTest(model=model.__name__, parent_delete=parent_delete):
                    participant = model.objects.create(user=self.user, tournament=tournament, rank=1, rank_score=100)
                    record = self.seed_scores()
                    with self.captureOnCommitCallbacks(execute=True):
                        if parent_delete:
                            TournamentParticipant.objects.filter(pk=participant.pk).delete()
                        else:
                            participant.delete()

                    record.refresh_from_db()
                    self.assertAlmostEqual(record.score_current, 125)
                    self.assertEqual(record.last_updated, self.last_updated)
                    self.assertEqual(record.score_total, 400)
                    self.assertEqual(record.gsc_total, 150 if category == 'gsc' else 250)
                    expected_weekly = 150 if category == 'weekly' else 250
                    self.assertEqual((record.weekly_total, record.weekly_classic_total), (expected_weekly, expected_weekly))
                    self.assert_cached_current_score(record)
                    self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], self.user.id), 400)
                    self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_total'], self.user.id), record.gsc_total)
                    self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_total'], self.user.id), record.weekly_total)
                    self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_total'], self.user.id), record.weekly_classic_total)

    def test_deleting_last_score_removes_zero_rankings_but_keeps_account(self):
        participant = GSCParticipant.objects.create(user=self.user, tournament=self.tournament, rank=1, rank_score=100)
        self.tournament.end_time = self.last_updated
        self.tournament.save(update_fields=['end_time'])
        record = self.seed_scores(current=100, total=100, gsc=100, weekly=0)
        participant_id = participant.pk

        with self.captureOnCommitCallbacks(execute=True):
            participant.delete()
            TournamentParticipant.objects.filter(pk=participant_id).delete()

        record.refresh_from_db()
        self.assertEqual((record.score_current, record.score_total, record.gsc_total), (0, 0, 0))
        self.assertEqual(record.last_updated, self.last_updated)
        self.assertTrue(TournamentUser.objects.filter(user_id=self.user.id).exists())
        for field in ('score_current', 'score_total', 'gsc_total'):
            self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS[field], self.user.id))

    def test_anonymous_and_unawarded_scores_do_not_call_add_score(self):
        for model, tournament in ((GSCParticipant, self.tournament), (WeeklyParticipant, self.weekly)):
            with self.subTest(model=model.__name__):
                anonymous = model.objects.create(tournament=tournament, rank=1, rank_score=100)
                unawarded = model.objects.create(user=self.user, tournament=tournament, rank_score=0)
                with patch.object(TournamentUser, 'add_score') as add_score:
                    anonymous.delete()
                    unawarded.delete()
                add_score.assert_not_called()

    def test_bulk_delete_accumulates_refunds_for_same_user(self):
        first = GSCParticipant.objects.create(user=self.user, tournament=self.tournament, rank=1, rank_score=100)
        second = WeeklyParticipant.objects.create(user=self.user, tournament=self.weekly, rank=1, rank_score=50)
        record = self.seed_scores(current=75, total=150, gsc=100, weekly=50)

        with self.captureOnCommitCallbacks(execute=True):
            TournamentParticipant.objects.filter(pk__in=[first.pk, second.pk]).delete()

        record.refresh_from_db()
        self.assertEqual((record.score_current, record.score_total, record.gsc_total), (0, 0, 0))
        self.assertEqual((record.weekly_total, record.weekly_classic_total), (0, 0))
        self.assertEqual(record.last_updated, self.last_updated)
        for field in ('score_current', 'score_total', 'gsc_total', 'weekly_total', 'weekly_classic_total'):
            self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS[field], self.user.id))

    def test_rollback_restores_participant_and_scores_without_publishing_refund(self):
        participant = GSCParticipant.objects.create(user=self.user, tournament=self.tournament, rank=1, rank_score=100)
        participant_id = participant.pk
        record = self.seed_scores()
        current_score = cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_current'], self.user.id)

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesMessage(RuntimeError, 'rollback deletion'):
                with transaction.atomic():
                    participant.delete()
                    self.assertEqual(TournamentUser.objects.get(user_id=self.user.id).score_total, 400)
                    self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], self.user.id), 500)
                    raise RuntimeError('rollback deletion')

        record.refresh_from_db()
        self.assertTrue(GSCParticipant.objects.filter(pk=participant_id).exists())
        self.assertEqual((record.score_current, record.score_total, record.gsc_total), (175, 500, 250))
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], self.user.id), 500)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_current'], self.user.id), current_score)

    def test_tournament_cascade_revokes_participant_scores(self):
        for model, tournament in ((GSCParticipant, self.tournament), (WeeklyParticipant, self.weekly)):
            with self.subTest(model=model.__name__):
                model.objects.create(user=self.user, tournament=tournament, rank=1, rank_score=100)
                record = self.seed_scores()
                with self.captureOnCommitCallbacks(execute=True):
                    tournament.delete()
                record.refresh_from_db()
                self.assertEqual((record.score_current, record.score_total), (125, 400))
                self.assert_cached_current_score(record)
