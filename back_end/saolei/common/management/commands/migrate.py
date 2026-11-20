from django.core.management.commands.migrate import Command as DjangoMigrateCommand
from django.db import connections


class Command(DjangoMigrateCommand):
    def execute(self, *args, **options):
        connection = connections[options['database']]
        if connection.vendor != 'mysql':
            return super().execute(*args, **options)

        original_options = connection.settings_dict['OPTIONS']
        # 已打开的连接不会读取新参数，迁移前重新建立连接。
        connection.close()
        connection.settings_dict['OPTIONS'] = {
            **original_options, 'read_timeout': 300, 'write_timeout': 300,
        }
        try:
            return super().execute(*args, **options)
        finally:
            connection.settings_dict['OPTIONS'] = original_options
            connection.close()
