from tournament.cache import TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY
from tournament.utils import tournament_score_reference_time
from .base import (
    award_tournament_rank_scores,
    cache,
    call_command,
    gsc_encode_best,
    GSCParticipant,
    GSCTournament,
    MAX_TOURNAMENT_BEST,
    refresh_weekly_best_scores,
    StringIO,
    timedelta,
    timezone,
    Tournament_TextChoices,
    TOURNAMENT_USER_CACHE_KEYS,
    TournamentTestCaseBase,
    TournamentUser,
    weekly_encode_best,
    WeeklyParticipant,
)


class TestScore(TournamentTestCaseBase):
    def test_tournament_user_defaults_and_best_score_encoding_helpers(self):
        tournament_user = TournamentUser.objects.create(user=self.user)

        self.assertEqual(tournament_user.score_current, 0)
        self.assertEqual(tournament_user.score_total, 0)
        self.assertEqual(tournament_user.gsc_total, 0)
        self.assertEqual(tournament_user.weekly_total, 0)
        self.assertEqual(tournament_user.weekly_classic_total, 0)
        self.assertEqual(tournament_user.gsc_best, MAX_TOURNAMENT_BEST)
        self.assertEqual(tournament_user.weekly_classic_best, MAX_TOURNAMENT_BEST)

        self.assertEqual(gsc_encode_best(123456, 7), 123456007)
        self.assertEqual(weekly_encode_best(345678, 2026, 12), 34567802612)

    def test_participant_create_signal_creates_tournament_user(self):
        other_user = self.create_user('tournament_user_prepare_other')
        tournament = self.create_weekly_tournament()
        TournamentUser.objects.create(user=self.user)
        WeeklyParticipant.objects.create(
            user=self.user,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        WeeklyParticipant.objects.create(
            user=other_user,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        WeeklyParticipant.objects.create(
            user=None,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )

        self.assertEqual(TournamentUser.objects.filter(user__in=[self.user, other_user]).count(), 2)

    def test_tournament_user_cache_rebuilds_sorted_sets_without_defaults(self):
        other_user = self.create_user('tournament_user_cache_other')
        default_user = self.create_user('tournament_user_cache_default')
        now = timezone.now()
        older_score = TournamentUser.objects.create(user=self.user, score_current=100, last_updated=now - timedelta(days=730))
        tournament_user = TournamentUser.objects.create(
            user=other_user,
            score_current=12.5,
            last_updated=now,
            score_total=100,
            gsc_total=60,
            gsc_best=gsc_encode_best(123456, 2),
            weekly_total=40,
            weekly_classic_total=30,
            weekly_classic_best=weekly_encode_best(345678, 2026, 4),
        )
        default_tournament_user = TournamentUser.objects.create(user=default_user, last_updated=now + timedelta(days=1))
        cache.set(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY, (now + timedelta(days=730)).isoformat())
        for key in TOURNAMENT_USER_CACHE_KEYS.values():
            cache.zadd(key, {'999999999': 500})

        stdout = StringIO()
        call_command('rebuild_tournament_user_cache', batch_size=1, stdout=stdout)

        self.assertIn('rebuilt 3 tournament user cache rows', stdout.getvalue())
        self.assertEqual(cache.get(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY).decode(), tournament_score_reference_time().isoformat())
        self.assert_cached_current_score(older_score)
        self.assert_cached_current_score(tournament_user)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], tournament_user.user_id), 100)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_total'], tournament_user.user_id), 60)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], tournament_user.user_id), tournament_user.gsc_best)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_total'], tournament_user.user_id), 40)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_total'], tournament_user.user_id), 30)
        self.assertEqual(
            cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_best'], tournament_user.user_id),
            tournament_user.weekly_classic_best,
        )
        for key in TOURNAMENT_USER_CACHE_KEYS.values():
            self.assertIsNone(cache.zscore(key, default_tournament_user.user_id))
            self.assertIsNone(cache.zscore(key, '999999999'))

        tournament_user.score_total = 0
        tournament_user.gsc_best = MAX_TOURNAMENT_BEST
        self.tournament_cache.update_tournament_user(tournament_user, fields=['score_total', 'gsc_best'])

        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], tournament_user.user_id))
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], tournament_user.user_id))
        self.tournament_cache.clear_tournament_user_cache()
        self.assertIsNone(cache.get(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY))
        for key in TOURNAMENT_USER_CACHE_KEYS.values():
            self.assertEqual(cache.zcard(key), 0)

    def test_award_tournament_rank_scores_decays_and_uses_delta(self):
        award_time = timezone.now()
        tournament = self.create_weekly_tournament(end_time=award_time, weight=50)
        tournament_user = TournamentUser.objects.create(
            user=self.user,
            score_current=100,
            last_updated=award_time - timedelta(days=365 * 2),
            score_total=100,
            weekly_total=100,
            weekly_classic_total=100,
        )
        participant = WeeklyParticipant.objects.create(
            user=self.user,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
            rank=1,
            rank_score=20,
        )
        WeeklyParticipant.objects.create(
            user=None,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
            rank=2,
        )
        TournamentUser.objects.filter(user=self.user).update(weekly_classic_best=MAX_TOURNAMENT_BEST)

        with self.captureOnCommitCallbacks(execute=True):
            award_count = award_tournament_rank_scores(tournament)

        participant.refresh_from_db()
        tournament_user.refresh_from_db()
        self.assertEqual(award_count, 1)
        self.assertEqual(participant.rank_score, 50)
        self.assertAlmostEqual(tournament_user.score_current, 80)
        self.assertEqual(tournament_user.score_total, 130)
        self.assertEqual(tournament_user.weekly_total, 130)
        self.assertEqual(tournament_user.weekly_classic_total, 130)
        self.assertEqual(tournament_user.last_updated, award_time)
        self.assertEqual(tournament_user.weekly_classic_best, MAX_TOURNAMENT_BEST)
        self.assertEqual(TournamentUser.objects.count(), 1)
        self.assert_cached_current_score(tournament_user)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], self.user.id), 130)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_total'], self.user.id), 130)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_total'], self.user.id), 130)
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_best'], self.user.id))

        tournament.state = Tournament_TextChoices.State.AWARDED
        tournament.save(update_fields=['state'])
        best_count = refresh_weekly_best_scores(tournament)

        tournament_user.refresh_from_db()
        self.assertEqual(best_count, 1)
        self.assertEqual(
            tournament_user.weekly_classic_best,
            weekly_encode_best(participant.classic_score, 2026, 1),
        )
        self.assertEqual(
            cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_best'], self.user.id),
            tournament_user.weekly_classic_best,
        )

    def test_weekly_participant_save_signal_refreshes_best_score(self):
        tournament = self.create_weekly_tournament(year=2026, week=2)
        tournament.state = Tournament_TextChoices.State.AWARDED
        tournament.save(update_fields=['state'])

        WeeklyParticipant.objects.create(
            user=self.user,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
            rank=1,
            rank_score=50,
            classic_score=123456,
        )

        tournament_user = TournamentUser.objects.get(user=self.user)
        self.assertEqual(
            tournament_user.weekly_classic_best,
            weekly_encode_best(123456, 2026, 2),
        )
        self.assertEqual(
            cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_best'], self.user.id),
            tournament_user.weekly_classic_best,
        )

    def test_gsc_participant_delete_signal_rebuilds_best_score(self):
        better_tournament = GSCTournament.objects.create(
            order=2,
            _token='G22222',
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
            state=Tournament_TextChoices.State.AWARDED,
        )
        worse_tournament = GSCTournament.objects.create(
            order=3,
            _token='G33333',
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
            state=Tournament_TextChoices.State.AWARDED,
        )
        better_participant = GSCParticipant.objects.create(
            user=self.user,
            tournament=better_tournament,
            token=better_tournament.token,
            start_time=better_tournament.start_time,
            end_time=better_tournament.end_time,
            rank=1,
            rank_score=1000,
            bt20sum=1000,
            it12sum=1000,
            et5sum=1000,
        )
        worse_participant = GSCParticipant.objects.create(
            user=self.user,
            tournament=worse_tournament,
            token=worse_tournament.token,
            start_time=worse_tournament.start_time,
            end_time=worse_tournament.end_time,
            rank=2,
            rank_score=500,
            bt20sum=2000,
            it12sum=2000,
            et5sum=2000,
        )

        tournament_user = TournamentUser.objects.get(user=self.user)
        self.assertEqual(
            tournament_user.gsc_best,
            gsc_encode_best(better_participant.t37, better_tournament.order),
        )
        self.assertEqual(
            cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], self.user.id),
            tournament_user.gsc_best,
        )

        TournamentUser.objects.filter(user=self.user).update(
            score_current=1500, score_total=1500, gsc_total=1500, last_updated=better_tournament.end_time,
        )
        better_participant.delete()

        tournament_user.refresh_from_db()
        worse_participant.refresh_from_db()
        self.assertEqual(
            tournament_user.gsc_best,
            gsc_encode_best(worse_participant.t37, worse_tournament.order),
        )
        self.assertEqual(
            cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], self.user.id),
            tournament_user.gsc_best,
        )

    def test_refresh_tournament_user_stats_command_rebuilds_total_and_best_only(self):
        other_user = self.create_user('stats_other')
        stale_user = self.create_user('stats_stale')
        weekly_tournament = self.create_weekly_tournament(year=2026, week=3)
        self.tournament.state = Tournament_TextChoices.State.AWARDED
        self.tournament.save(update_fields=['state'])
        weekly_tournament.state = Tournament_TextChoices.State.AWARDED
        weekly_tournament.save(update_fields=['state'])
        last_updated = timezone.now() - timedelta(days=10)
        TournamentUser.objects.create(
            user=self.user,
            score_current=42,
            last_updated=last_updated,
            score_total=999,
            gsc_total=999,
            gsc_best=999,
            weekly_total=999,
            weekly_classic_total=999,
            weekly_classic_best=999,
        )

        gsc_participant = GSCParticipant.objects.create(
            user=self.user,
            tournament=self.tournament,
            token=self.tournament.token,
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
            rank=1,
            rank_score=10,
            bt20sum=1000,
            it12sum=2000,
            et5sum=3000,
        )
        weekly_participant = WeeklyParticipant.objects.create(
            user=self.user,
            tournament=weekly_tournament,
            start_time=weekly_tournament.start_time,
            end_time=weekly_tournament.end_time,
            rank=1,
            rank_score=20,
            classic_score=123456,
        )
        GSCParticipant.objects.create(
            user=other_user,
            tournament=self.tournament,
            token='other-token',
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
            rank=2,
            rank_score=5,
            bt20sum=2000,
            it12sum=3000,
            et5sum=4000,
        )
        TournamentUser.objects.filter(user=self.user).update(
            score_current=42,
            last_updated=last_updated,
            score_total=999,
            gsc_total=999,
            gsc_best=999,
            weekly_total=999,
            weekly_classic_total=999,
            weekly_classic_best=999,
        )
        TournamentUser.objects.create(
            user=stale_user,
            score_current=24,
            score_total=888,
            gsc_total=888,
            gsc_best=888,
            weekly_total=888,
            weekly_classic_total=888,
            weekly_classic_best=888,
        )

        stdout = StringIO()
        call_command('refresh_tournament_user_stats', stdout=stdout)

        tournament_user = TournamentUser.objects.get(user=self.user)
        self.assertEqual(tournament_user.score_current, 42)
        self.assertEqual(tournament_user.last_updated, last_updated)
        self.assertEqual(tournament_user.score_total, 30)
        self.assertEqual(tournament_user.gsc_total, 10)
        self.assertEqual(tournament_user.weekly_total, 20)
        self.assertEqual(tournament_user.weekly_classic_total, 20)
        self.assertEqual(
            tournament_user.gsc_best,
            gsc_encode_best(gsc_participant.t37, self.tournament.order),
        )
        self.assertEqual(
            tournament_user.weekly_classic_best,
            weekly_encode_best(weekly_participant.classic_score, 2026, 3),
        )
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], self.user.id), 30)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_total'], self.user.id), 10)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_total'], self.user.id), 20)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_total'], self.user.id), 20)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], self.user.id), tournament_user.gsc_best)
        self.assertEqual(
            cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_best'], self.user.id),
            tournament_user.weekly_classic_best,
        )

        other_tournament_user = TournamentUser.objects.get(user=other_user)
        self.assertEqual(other_tournament_user.score_total, 5)
        self.assertEqual(other_tournament_user.gsc_total, 5)
        self.assertEqual(other_tournament_user.weekly_total, 0)
        self.assertEqual(other_tournament_user.weekly_classic_total, 0)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], other_user.id), 5)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_total'], other_user.id), 5)
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_total'], other_user.id))
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_total'], other_user.id))

        stale_tournament_user = TournamentUser.objects.get(user=stale_user)
        self.assertEqual(stale_tournament_user.score_current, 24)
        self.assertEqual(stale_tournament_user.score_total, 0)
        self.assertEqual(stale_tournament_user.gsc_total, 0)
        self.assertEqual(stale_tournament_user.gsc_best, MAX_TOURNAMENT_BEST)
        self.assertEqual(stale_tournament_user.weekly_total, 0)
        self.assertEqual(stale_tournament_user.weekly_classic_total, 0)
        self.assertEqual(stale_tournament_user.weekly_classic_best, MAX_TOURNAMENT_BEST)
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], stale_user.id))
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_total'], stale_user.id))
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], stale_user.id))
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_total'], stale_user.id))
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_total'], stale_user.id))
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_best'], stale_user.id))
        self.assertIn('refreshed 3 tournament user totals', stdout.getvalue())
        self.assertIn('refreshed 3 tournament user bests', stdout.getvalue())
