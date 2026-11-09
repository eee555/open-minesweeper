import os
from pathlib import Path
import shutil
import subprocess

import pytest


STOP_SCRIPT = Path(__file__).resolve().parents[1] / 'stop.sh'


@pytest.fixture
def bash_path():
    if os.name == 'nt':
        git = shutil.which('git')
        bash = Path(git).resolve().parents[1] / 'bin/bash.exe' if git else None
        if bash and bash.is_file():
            return str(bash)
        pytest.skip('Git Bash is required for shell script tests on Windows.')
    bash = shutil.which('bash')
    if not bash:
        pytest.skip('Bash is required for shell script tests.')
    return bash


def test_stop_script_terminates_launchers_and_service_processes(bash_path):
    """仍处于启动延迟中的 launcher 若没被终止，会用旧代码拉起 db_worker。"""
    env = os.environ.copy()
    env['STOP_DRY_RUN'] = '1'
    env['STOP_GRACE_SECONDS'] = '0'
    result = subprocess.run(
        [bash_path, STOP_SCRIPT.as_posix()],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert 'pkill -9 uwsgi' in result.stdout
    assert 'pkill -TERM -f [r]un_background' in result.stdout
    assert 'pkill -TERM -f ([d]b_worker|[r]unapscheduler)' in result.stdout
    assert 'pkill -KILL -f [r]un_background' in result.stdout
    assert 'pkill -KILL -f ([d]b_worker|[r]unapscheduler)' in result.stdout
    assert 'Background services stopped.' in result.stdout
    assert 'pgrep -f' in STOP_SCRIPT.read_text(encoding='utf-8')
