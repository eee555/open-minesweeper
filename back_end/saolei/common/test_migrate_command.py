from unittest import TestCase
from unittest.mock import Mock, patch

from django.core.management.commands.migrate import Command as DjangoMigrateCommand
from django.db.utils import ConnectionHandler

from common.management.commands.migrate import Command


class MigrateTimeoutTests(TestCase):
    def setUp(self):
        self.connections = ConnectionHandler({
            alias: {
                'ENGINE': 'django.db.backends.mysql', 'NAME': 'unused',
                'OPTIONS': {'connect_timeout': 5, 'read_timeout': 15, 'write_timeout': 15},
            }
            for alias in ['default', 'archive']
        })
        self.connection = self.connections['archive']
        self.connection.close = Mock()
        self.original_options = self.connection.settings_dict['OPTIONS']
        self.connection_patch = patch('common.management.commands.migrate.connections', self.connections)
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)

    def test_selected_mysql_database_uses_five_minutes_and_restores_normal_options(self):
        def execute(*args, **options):
            self.connection.close.assert_called_once_with()
            params = self.connection.get_connection_params()
            self.assertEqual((params['read_timeout'], params['write_timeout']), (300, 300))
            self.assertEqual(params['connect_timeout'], 5)
            self.assertEqual(self.connections['default'].settings_dict['OPTIONS'], self.original_options)
            self.assertEqual(args, ('videomanager',))
            self.assertEqual(options, {'database': 'archive', 'plan': True})
            return 'migration result'

        with patch.object(DjangoMigrateCommand, 'execute', side_effect=execute):
            result = Command().execute('videomanager', database='archive', plan=True)
        self.assertEqual(result, 'migration result')
        self.assertIs(self.connection.settings_dict['OPTIONS'], self.original_options)
        self.assertEqual(self.connection.get_connection_params()['read_timeout'], 15)
        self.assertEqual(self.connection.close.call_count, 2)

    def test_migration_failure_restores_options_and_closes_the_long_timeout_connection(self):
        with patch.object(DjangoMigrateCommand, 'execute', side_effect=RuntimeError('migration failed')):
            with self.assertRaisesRegex(RuntimeError, 'migration failed'):
                Command().execute(database='archive')
        self.assertIs(self.connection.settings_dict['OPTIONS'], self.original_options)
        self.assertEqual(self.connection.get_connection_params()['write_timeout'], 15)
        self.assertEqual(self.connection.close.call_count, 2)

    def test_non_mysql_database_keeps_its_connection_and_options(self):
        connection = Mock(vendor='sqlite', settings_dict={'OPTIONS': {'timeout': 5}})
        with patch('common.management.commands.migrate.connections', {'default': connection}):
            with patch.object(DjangoMigrateCommand, 'execute', return_value='sqlite result') as execute:
                self.assertEqual(Command().execute(database='default'), 'sqlite result')
        execute.assert_called_once_with(database='default')
        self.assertEqual(connection.settings_dict['OPTIONS'], {'timeout': 5})
        connection.close.assert_not_called()
