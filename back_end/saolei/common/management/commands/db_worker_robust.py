import json
import os
from pathlib import Path
import socket
import time
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.tasks import DEFAULT_TASK_BACKEND_ALIAS, TaskResultStatus
from django.tasks.base import DEFAULT_TASK_QUEUE_NAME
from django.utils import timezone
from django_tasks_db.models import DBTaskResult
import psutil

WORKER_COMMANDS = {'db_worker', 'db_worker_robust'}
PIDFILE_STARTED_TOLERANCE_SECONDS = 120


def _cmdline_runs_worker(cmdline: list[str]) -> bool:
    return any(Path(arg).name in WORKER_COMMANDS for arg in cmdline)


def _ancestor_pids(pid: int) -> set[int]:
    # Windows 的 venv 启动器会留下一个命令行相同的父进程。它不是另一个 worker。
    try:
        return {parent.pid for parent in psutil.Process(pid).parents()}
    except psutil.Error:
        return set()


def iter_running_worker_processes(exclude_pid: int | None = None):
    current_pid = os.getpid() if exclude_pid is None else exclude_pid
    excluded = {current_pid, *_ancestor_pids(current_pid)}
    for process in psutil.process_iter(['pid', 'cmdline', 'create_time']):
        try:
            if process.info['pid'] in excluded:
                continue
            cmdline = process.info.get('cmdline') or []
        except psutil.Error:
            continue
        if _cmdline_runs_worker(cmdline):
            yield process


def _process_matches_pidfile(pid: int, started_at: int) -> bool:
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False
    except psutil.Error:
        return True

    try:
        process_started_at = int(process.create_time())
    except psutil.Error:
        return True
    if abs(process_started_at - started_at) > PIDFILE_STARTED_TOLERANCE_SECONDS:
        return False

    try:
        return _cmdline_runs_worker(process.cmdline())
    except psutil.Error:
        return True


def _read_pidfile(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None


def acquire_pidfile(path: Path, worker_id: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    content = json.dumps({
        'pid': os.getpid(),
        'started_at': now,
        'worker_id': worker_id,
    })

    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing = _read_pidfile(path)
            if existing:
                try:
                    pid = int(existing.get('pid', 0))
                    started_at = int(existing.get('started_at', 0))
                except (TypeError, ValueError):
                    pid = 0
                    started_at = 0
                if _process_matches_pidfile(pid, started_at):
                    return False
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                return False
            continue

        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    return False


def release_pidfile(path: Path):
    existing = _read_pidfile(path)
    if existing and existing.get('pid') != os.getpid():
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def build_worker_id() -> str:
    hostname = socket.gethostname().split('.')[0] or 'localhost'
    hostname = hostname[:32]
    try:
        started_at = int(psutil.Process(os.getpid()).create_time())
    except psutil.Error:
        started_at = int(time.time())
    return f'{hostname}-{os.getpid()}-{started_at}'


def fail_orphaned_running_tasks() -> int:
    now = timezone.now()
    return DBTaskResult.objects.filter(status=TaskResultStatus.RUNNING).update(
        status=TaskResultStatus.FAILED,
        finished_at=now,
        return_value=None,
        exception_class_path='builtins.RuntimeError',
        traceback=(
            f'Marked FAILED by db_worker_robust at {now.isoformat()} because no '
            'running db_worker process was detected before startup.'
        ),
    )


class Command(BaseCommand):
    help = 'Fail orphaned RUNNING tasks, then start django-tasks-db worker safely.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--queue-name',
            default=DEFAULT_TASK_QUEUE_NAME,
            help="The queues to process. Separate multiple with a comma. Use '*' for all queues.",
        )
        parser.add_argument(
            '--interval',
            type=float,
            default=2,
            help='Worker polling interval in seconds.',
        )
        parser.add_argument(
            '--backend',
            default=DEFAULT_TASK_BACKEND_ALIAS,
            dest='backend_name',
            help='Task backend to operate on.',
        )
        parser.add_argument(
            '--batch',
            action='store_true',
            help='Pass --batch to db_worker.',
        )
        parser.add_argument(
            '--no-startup-delay',
            action='store_false',
            dest='startup_delay',
            help='Pass --no-startup-delay to db_worker.',
        )
        parser.add_argument(
            '--max-tasks',
            type=int,
            default=None,
            help='Pass --max-tasks to db_worker.',
        )
        parser.add_argument(
            '--worker-id',
            default=None,
            help='Override generated worker id.',
        )
        parser.add_argument(
            '--pidfile',
            default='logs/db_worker_robust.pid',
            help='Pidfile used to prevent duplicate robust workers.',
        )

    def handle(self, *args, **options):
        worker_id = options['worker_id'] or build_worker_id()
        pidfile = Path(options['pidfile'])

        if not acquire_pidfile(pidfile, worker_id):
            self.stdout.write(self.style.WARNING(
                f'Another db_worker_robust appears to be running; pidfile={pidfile}.',
            ))
            return

        try:
            worker_processes = list(iter_running_worker_processes())
            if worker_processes:
                pids = ', '.join(str(process.info['pid']) for process in worker_processes)
                self.stdout.write(self.style.WARNING(
                    f'Existing db_worker process detected, exiting without changes. pids={pids}',
                ))
                return

            failed_count = fail_orphaned_running_tasks()
            if failed_count:
                self.stdout.write(self.style.WARNING(
                    f'Marked {failed_count} orphaned RUNNING task(s) as FAILED.',
                ))

            call_command(
                'db_worker',
                queue_name=options['queue_name'],
                interval=options['interval'],
                batch=options['batch'],
                reload=False,
                backend_name=options['backend_name'],
                startup_delay=options['startup_delay'],
                max_tasks=options['max_tasks'],
                worker_id=worker_id,
                verbosity=options['verbosity'],
                skip_checks=True,
            )
        finally:
            release_pidfile(pidfile)
