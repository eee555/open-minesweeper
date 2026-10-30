from datetime import datetime, timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from config.tournaments import TournamentWeights
from customranking.services import add_videos_to_custom_pluck_ranks
from identifier.models import Identifier
from msuser.models import UserMS
from msuser.services import update_video_count_limit_from_videos
from tournament.models import WeeklyTournament
from userprofile.models import UserProfile
from videomanager.cache import add_videos_to_state_queues_bulk
from videomanager.models import ExpandVideoModel, MAX_TIMEMS, VideoModel
from .cache import get_local_snapshot_cache, reset_local_snapshot_cache
from .utils import snapshot_pages, validate_snapshot


USER_FIELDS = ('id', 'username', 'firstname', 'lastname', 'realname', 'signature', 'country', 'is_banned', 'left_avatar_n', 'left_signature_n')
VIDEO_FIELDS = (
    'id', 'software', 'level', 'mode', 'state', 'timems', 'bv', 'path', 'pluck', 'flag', 'op', 'isl', 'file_size',
    'left', 'right', 'double', 'left_ce', 'right_ce', 'double_ce',
    'cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6', 'cell7', 'cell8',
)
USER_DATES = ('last_change_avatar', 'last_change_signature')


def snapshot_datetime(value):
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        raise ValueError('Snapshot timestamps must include a timezone')
    return parsed


def video_from_snapshot(row):
    values = {name: row[name] for name in VIDEO_FIELDS if name in row}
    # Older snapshots may store the legacy NF mode; keep the supplied right_ce.
    if values['mode'] == '12':
        values['mode'] = MS_TextChoices.Mode.STD
    if not 0 <= values['timems'] <= MAX_TIMEMS:
        raise ValueError(f'Video {row["id"]}: timems is out of range')
    return VideoModel(
        **values, player_id=row['player'], video_id=row['id'],
        file=f'videos/public-snapshot/{row["id"]}.missing',
        upload_time=snapshot_datetime(row['upload_time']),
        end_time=snapshot_datetime(row['end_time']) if row.get('end_time') else None,
    )


def validate_import(root, manifest, users):
    """在清空本地数据库前检查账号和可解析的模型数据。"""
    if not {2, 48}.issubset(users):
        raise ValueError('Snapshot must contain account IDs 2 and 48')
    for row in users.values():
        for field in USER_DATES:
            if row.get(field):
                snapshot_datetime(row[field])
    for rows in snapshot_pages(root, manifest, 'videos'):
        for row in rows:
            video_from_snapshot(row)


@transaction.atomic
def import_snapshot_rows(root, manifest, users, admin_password, user_password):
    """批量导入公开元数据；不触发逐录像信号，随后由调用方重建派生数据。"""
    UserMS.objects.bulk_create([UserMS(id=user_id, identifiers=row['identifiers']) for user_id, row in users.items()], batch_size=500)
    profiles = []
    for row in users.values():
        profile = UserProfile(**{name: row[name] for name in USER_FIELDS if name in row})
        profile.userms_id = profile.id
        profile.email = f'user-{profile.id}@example.invalid'
        profile.is_staff = profile.id == 2
        if profile.id in (2, 48):
            profile.set_password(admin_password if profile.id == 2 else user_password)
        else:
            profile.set_unusable_password()
        profiles.append(profile)
    UserProfile.objects.bulk_create(profiles, batch_size=500)
    for profile in profiles:
        for field in USER_DATES:
            if value := users[profile.id].get(field):
                setattr(profile, field, snapshot_datetime(value))
    UserProfile.objects.bulk_update(profiles, USER_DATES, batch_size=500)

    # Restore both sides together, preserving snapshot video states; derived data is rebuilt after the import.
    Identifier.objects.bulk_create([
        Identifier(identifier=identifier, userms_id=user_id, safe=True)
        for user_id, row in users.items() for identifier in row['identifiers']
    ], batch_size=500)

    for rows in snapshot_pages(root, manifest, 'videos'):
        ExpandVideoModel.objects.bulk_create([
            ExpandVideoModel(id=row['id'], identifier=row.get('video__identifier') or '') for row in rows
        ], batch_size=500)
        videos = [video_from_snapshot(row) for row in rows]
        VideoModel.objects.bulk_create(videos, batch_size=500)
        # auto_now_add also runs during bulk_create; restore the original tie-breaker.
        for video, row in zip(videos, rows):
            video.upload_time = snapshot_datetime(row['upload_time'])
        VideoModel.objects.bulk_update(videos, ['upload_time'], batch_size=500)


def create_local_weekly_tournament():
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    year, week, _ = start.isocalendar()
    return WeeklyTournament.objects.create(
        year=year, week=week, host_id=2,
        start_time=start, end_time=start + timedelta(days=1),
        state=Tournament_TextChoices.State.NORMAL,
        weight=TournamentWeights.WEEKLY,
        subclass=Tournament_TextChoices.Subclass.WEEKLY,
        tournament_format=Tournament_TextChoices.WeeklyFormat.CLASSIC,
    )


def initialize_local_data(root, admin_password, user_password, *, stdout, create_weekly=True):
    """仅供本地初始化脚本调用，拒绝生产标记及非本地测试配置。"""
    if settings.PRODUCTION_MARK.exists() or not settings.DEBUG or not settings.E2E_TEST:
        raise CommandError('Requires a local test environment without .production, DEBUG and E2E_TEST; never use on production')
    if connection.settings_dict.get('HOST') not in ('localhost', '127.0.0.1', '::1'):
        raise CommandError('Snapshot import requires a loopback database connection')
    if not admin_password or not user_password:
        raise CommandError('Both test account passwords must be nonempty')
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise CommandError('Run manage.py migrate before importing; no data was cleared')
    try:
        manifest, users = validate_snapshot(root)
        validate_import(root, manifest, users)
        get_local_snapshot_cache()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CommandError(f'Preflight failed; no data was cleared: {error}') from error

    stdout.write(f'Validated {len(users)} users and {manifest["video_count"]} videos. Resetting local data.\n')
    if manifest['version'] == 1:
        stdout.write('Legacy snapshot has no user identifiers; rerun download_public_data to add them.\n')
    if missing := manifest.get('missing_detail_video_ids'):
        stdout.write(f'{len(missing)} videos use list data only; missing metrics remain NULL and identifiers remain empty. Supplied right_ce is preserved for NF rankings.\n')
    call_command('flush', interactive=False, verbosity=0)
    reset_local_snapshot_cache()
    import_snapshot_rows(root, manifest, users, admin_password, user_password)
    stdout.write('Imported rows; rebuilding counts, quotas and caches.\n')
    call_command('refresh_video_counts', stdout=stdout)
    for user in UserProfile.objects.select_related('userms').iterator(chunk_size=500):
        update_video_count_limit_from_videos(user.userms, VideoModel.objects.filter(player=user))
    call_command('rebuild_speed_ranks', stdout=stdout)
    call_command('rebuild_pb_ranks', stdout=stdout)
    call_command('rebuild_top_ranks', stdout=stdout)
    call_command('rebuild_eff_ranks', stdout=stdout)
    call_command('rebuild_eff_ranks', ranking_name='nf_ioe', stdout=stdout)
    add_videos_to_custom_pluck_ranks(VideoModel.objects.all())
    for rows in snapshot_pages(root, manifest, 'videos'):
        add_videos_to_state_queues_bulk(VideoModel.objects.filter(id__in=[row['id'] for row in rows]).select_related('player', 'video'))
    if create_weekly:
        tournament = create_local_weekly_tournament()
        stdout.write(f'Weekly tournament: id={tournament.id}, start={tournament.start_time}, end={tournament.end_time}\n')
    stdout.write(f'Imported {len(users)} users, {manifest["video_count"]} videos and {manifest.get("identifier_count", 0)} identifiers.\n')
    stdout.write(f'Admin: id=2, username={users[2]["username"]}; normal user: id=48, username={users[48]["username"]}\n')
