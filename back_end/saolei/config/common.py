from datetime import timedelta


TASK_CLEANUP_CONFIGS = [
    {
        'task_path': 'accountlink.saolei.tasks.task_import_saolei_hourly',
        'expires': timedelta(days=7),
    },
    {
        'task_path': 'videomanager.tasks.task_video_pluck',
        'expires': timedelta(days=1),
    },
    {
        'task_path': 'accountlink.tasks.task_saolei_video_import',
        'expires': timedelta(days=7),
    },
    {
        'task_path': 'accountlink.tasks.task_saolei_video_import_bulk',
        'expires': timedelta(days=7),
    },
    {
        'task_path': 'speedranking.top.tasks.task_refresh_soft_ranks',
        'expires': timedelta(days=7),
    },
    {
        'task_path': 'tournament.gsc.tasks.task_gsc_finish',
        'expires': timedelta(days=30),
    },
]
