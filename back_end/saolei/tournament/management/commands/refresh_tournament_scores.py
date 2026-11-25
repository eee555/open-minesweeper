from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from config.text_choices import Tournament_TextChoices
from tournament.gsc.services import refresh_gsc_best_scores, refresh_gsc_scores
from tournament.models import GSCTournament, Tournament, WeeklyEffTournament, WeeklyTournament
from tournament.services import award_tournament_rank_scores, ensure_tournament_users, refresh_tournament_ranks
from tournament.weekly.services import refresh_weekly_best_scores, refresh_weekly_scores
from tournament.weekly_eff.services import refresh_weekly_eff_best_scores, refresh_weekly_eff_scores


class Command(BaseCommand):
    help = '重算指定已颁奖比赛的成绩、排名、积分和个人历史最佳成绩，支持 GSC、竞速及效率打卡赛'

    def add_arguments(self, parser):
        parser.add_argument('tournament_id', type=int, help='比赛 ID，不是 GSC 届数或周数')
        parser.add_argument('--batch-size', type=int, default=1000, help='批量写入大小，默认 1000')

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        if batch_size <= 0:
            raise CommandError('batch-size 必须为正整数')
        try:
            tournament = Tournament.objects.select_subclasses().get(pk=options['tournament_id'])
        except Tournament.DoesNotExist as exc:
            raise CommandError(f"比赛#{options['tournament_id']}不存在") from exc
        if tournament.state != Tournament_TextChoices.State.AWARDED or tournament.end_time is None:
            raise CommandError('只能重算已颁奖且有结束时间的比赛')
        if isinstance(tournament, GSCTournament):
            refresh_scores = refresh_gsc_scores
            refresh_best_scores = refresh_gsc_best_scores
            name = f'GSC#{tournament.order}'
        elif isinstance(tournament, WeeklyEffTournament):
            refresh_scores = refresh_weekly_eff_scores
            refresh_best_scores = refresh_weekly_eff_best_scores
            name = f'效率打卡赛（{tournament.year}W{tournament.week}）'
        elif isinstance(tournament, WeeklyTournament):
            if tournament.tournament_format not in Tournament_TextChoices.WeeklyFormat.values:
                raise CommandError('不支持的竞速打卡赛赛制')
            refresh_scores = refresh_weekly_scores
            refresh_best_scores = refresh_weekly_best_scores
            name = tournament.name['zh']
        else:
            raise CommandError('当前只支持 GSC、竞速及效率打卡赛')

        self.stdout.write(f'开始重算比赛#{tournament.id}：{name}')
        with transaction.atomic():
            ensure_tournament_users(tournament)
            score_count = refresh_scores(tournament, batch_size=batch_size)
            self.stdout.write(f'已刷新 {score_count} 个参赛者的成绩')
            rank_count = refresh_tournament_ranks(tournament, batch_size=batch_size)
            self.stdout.write(f'已刷新 {rank_count} 个参赛者的排名')
            award_count = award_tournament_rank_scores(tournament, batch_size=batch_size)
            self.stdout.write(f'已刷新 {award_count} 个参赛者的积分')
            best_count = refresh_best_scores(tournament, batch_size=batch_size, rebuild=True)
        self.stdout.write(self.style.SUCCESS(f'重算完成，已修正 {best_count} 个用户的历史最佳成绩'))
