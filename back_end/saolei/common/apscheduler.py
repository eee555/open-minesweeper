from datetime import timezone
import logging

from apscheduler.triggers.cron import CronTrigger
from captcha.models import CaptchaStore
from django.utils import timezone as django_timezone
from django_apscheduler import util
from django_apscheduler.models import DjangoJob, DjangoJobExecution

from accountlink.saolei.services import sync_saolei_metadata_daily
from accountlink.saolei.tasks import enqueue_missing_initial_sync, enqueue_saolei_hourly_import
from monitor.services import publish_monitor_snapshot
from tournament.cache import TournamentCache
from userprofile.models import EmailVerifyRecord
from videomanager.services import delete_newest_queue
from .services import cleanup_expired_tasks

logger = logging.getLogger(__name__)


@util.close_old_connections
def sync_saolei_daily_catalogue():
    sync_saolei_metadata_daily()


@util.close_old_connections
def queue_saolei_hourly_import():
    enqueue_saolei_hourly_import()


@util.close_old_connections
def queue_saolei_initial_sync_backfill():
    enqueue_missing_initial_sync()


@util.close_old_connections
def refresh_monitor_snapshot():
    publish_monitor_snapshot()


@util.close_old_connections
def delete_overdue_emailverifyrecord():
    start = django_timezone.now() - django_timezone.timedelta(seconds=3600)
    EmailVerifyRecord.objects.filter(send_time__lt=start).delete()


@util.close_old_connections
def delete_overdue_captcha():
    CaptchaStore.objects.filter(expiration__lt=django_timezone.now()).delete()


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


@util.close_old_connections
def delete_overdue_tasks():
    deleted_count = cleanup_expired_tasks(delete_all=True)
    logger.info('Deleted expired background tasks: count=%s', deleted_count)


@util.close_old_connections
def refresh_tournament_score_reference():
    changed = TournamentCache().refresh_tournament_score_reference()
    logger.info('Tournament score annual reference refreshed: changed=%s', changed)


def register_jobs(scheduler):
    # Remove the persisted job before the job store restores its deleted callable.
    DjangoJob.objects.filter(id__in=['refresh_state_always', 'delete_freezed_video', 'sync_saolei_daily']).delete()

    scheduler.add_job(
        sync_saolei_daily_catalogue,
        trigger=CronTrigger(hour=3, minute=30, timezone=scheduler.timezone),
        id='sync_saolei_metadata_daily', misfire_grace_time=3600, coalesce=True, max_instances=1, replace_existing=True,
    )
    scheduler.add_job(
        queue_saolei_hourly_import,
        trigger=CronTrigger(minute=0, timezone=scheduler.timezone),
        id='import_saolei_hourly', misfire_grace_time=600, coalesce=True, max_instances=1, replace_existing=True,
    )
    # 绑定后初始全量同步的兜底补队：入队失败或功能上线前的存量绑定由这里补齐；
    # 任务内 initial_sync_at 原子占坑，重复入队的任务立即退出。放在每日增量之后，错开上游配额。
    scheduler.add_job(
        queue_saolei_initial_sync_backfill,
        trigger=CronTrigger(hour=3, minute=40, timezone=scheduler.timezone),
        id='saolei_initial_sync_backfill', misfire_grace_time=3600, coalesce=True, max_instances=1, replace_existing=True,
    )

    scheduler.add_job(
        refresh_monitor_snapshot,
        trigger=CronTrigger(minute='*/5', second=0, timezone=scheduler.timezone),
        id='refresh_monitor_snapshot',
        next_run_time=django_timezone.now(),
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Added job 'refresh_monitor_snapshot'.")

    scheduler.add_job(
        refresh_tournament_score_reference,
        trigger=CronTrigger(month=1, day=1, hour=0, minute=0, second=0, timezone=timezone.utc),
        id='refresh_tournament_score_reference',
        # 启动时补一次幂等检查，避免跨年停机或错过执行时间后一直保留旧年锚点。
        next_run_time=django_timezone.now(),
        misfire_grace_time=None,
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Added annual job 'refresh_tournament_score_reference'.")

    scheduler.add_job(
        delete_old_job_executions,
        trigger=CronTrigger(hour='00', minute='03'),
        id='delete_old_job_executions',
        misfire_grace_time=30,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Added weekly job: 'delete_old_job_executions'.")

    scheduler.add_job(
        delete_newest_queue,
        trigger=CronTrigger(day_of_week='*', hour='01', minute='08'),
        id='delete_newest_queue',
        misfire_grace_time=300,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Added job 'delete_newest_queue'.")

    scheduler.add_job(
        delete_overdue_emailverifyrecord,
        trigger=CronTrigger(day_of_week='mon', hour='01', minute='03'),
        id='delete_overdue_emailverifyrecord',
        misfire_grace_time=30,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Added job 'delete_overdue_emailverifyrecord'.")

    scheduler.add_job(
        delete_overdue_captcha,
        trigger=CronTrigger(day_of_week='mon', hour='01', minute='05'),
        id='delete_overdue_captcha',
        misfire_grace_time=30,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Added job 'delete_overdue_captcha'.")

    scheduler.add_job(
        delete_overdue_tasks,
        trigger=CronTrigger(day_of_week='mon', hour='01', minute='10', timezone=scheduler.timezone),
        id='delete_overdue_tasks',
        misfire_grace_time=300,
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Added weekly job 'delete_overdue_tasks'.")
