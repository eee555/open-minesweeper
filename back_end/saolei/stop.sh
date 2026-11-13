#!/bin/bash
# 停止 uWSGI 与后台服务。
# 后台服务由 run_background.sh 延迟拉起：只杀 db_worker / runapscheduler 时，
# 仍处于启动延迟中的 launcher 会在部署后重新拉起旧版本进程，导致新任务被旧代码消费。
set -u

# 方括号写法避免 pkill / pgrep 匹配到自身命令行（含 sudo 父进程）。
LAUNCHER_PATTERN='[r]un_background\.sh'
SERVICE_PATTERN='([d]b_worker|[r]unapscheduler)'
ALL_PATTERN="($LAUNCHER_PATTERN|$SERVICE_PATTERN)"

as_root() {
    # dry-run 只打印命令并把 pgrep 视为「无残留」，供预览与静态测试使用。
    if [ -n "${STOP_DRY_RUN:-}" ]; then
        printf '%s\n' "$*"
        case "$1" in
            pgrep) return 1 ;;
            *) return 0 ;;
        esac
    fi
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

stop_pattern() {
    as_root pkill -TERM -f "$1" 2>/dev/null || true
}

as_root pkill -9 uwsgi || true
stop_pattern "$LAUNCHER_PATTERN"
stop_pattern "$SERVICE_PATTERN"

# db_worker 收到 TERM 会等当前任务结束；留出宽限时间后强杀残留。
sleep "${STOP_GRACE_SECONDS:-5}"
as_root pkill -KILL -f "$LAUNCHER_PATTERN" 2>/dev/null || true
as_root pkill -KILL -f "$SERVICE_PATTERN" 2>/dev/null || true

if as_root pgrep -f "$ALL_PATTERN" >/dev/null 2>&1; then
    echo 'Background services are still running after stop.sh; check the processes below.' >&2
    as_root pgrep -af "$ALL_PATTERN" >&2 || true
    exit 1
fi
echo 'Background services stopped.'
