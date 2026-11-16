from django.core.management.base import BaseCommand

from config.text_choices import Tournament_TextChoices
from tournament.cache import TournamentCache
from tournament.gsc.services import calculate_gsc_best_score
from tournament.models import TournamentParticipant, TournamentUser
from tournament.services import refresh_tournament_user_total_fields
from tournament.weekly.services import calculate_weekly_classic_best
from tournament.weekly_eff.services import calculate_weekly_eff_best
from tournament.weekly_eff.utils import WEEKLY_EFF_BEST_FIELDS


def refresh_tournament_user_best_fields(*, batch_size=1000):

    user_ids = (
        set(TournamentUser.objects.values_list('user_id', flat=True))
        | set(TournamentParticipant.objects.filter(user_id__isnull=False, tournament__state=Tournament_TextChoices.State.AWARDED).values_list('user_id', flat=True))
    )
    existing_user_ids = set(TournamentUser.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True))
    missing_user_ids = user_ids - existing_user_ids
    if missing_user_ids:
        TournamentUser.objects.bulk_create(
            [TournamentUser(user_id=user_id) for user_id in missing_user_ids],
            batch_size=batch_size,
        )

    tournament_users = list(TournamentUser.objects.filter(user_id__in=user_ids))
    for tournament_user in tournament_users:
        user_id = tournament_user.user_id
        tournament_user.gsc_best = calculate_gsc_best_score(user_id)
        tournament_user.weekly_classic_best = calculate_weekly_classic_best(user_id)
        for field, value in zip(WEEKLY_EFF_BEST_FIELDS, calculate_weekly_eff_best(user_id)):
            setattr(tournament_user, field, value)

    if tournament_users:
        TournamentUser.objects.bulk_update(
            tournament_users,
            ['gsc_best', 'weekly_classic_best', *WEEKLY_EFF_BEST_FIELDS],
            batch_size=batch_size,
        )
        TournamentCache().update_tournament_users(tournament_users, fields=['gsc_best', 'weekly_classic_best', *WEEKLY_EFF_BEST_FIELDS])

    return len(tournament_users)


class Command(BaseCommand):
    help = '刷新 TournamentUser 的历史 total 和 best 字段，不修改实时 score_current'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=1000)

    def handle(self, *args, **options):
        total_count = refresh_tournament_user_total_fields(batch_size=options['batch_size'])
        best_count = refresh_tournament_user_best_fields(batch_size=options['batch_size'])
        self.stdout.write(self.style.SUCCESS(
            f'refreshed {total_count} tournament user totals',
        ))
        self.stdout.write(self.style.SUCCESS(
            f'refreshed {best_count} tournament user bests',
        ))
