from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import override_settings, skipUnlessDBFeature, TransactionTestCase

from . import cache
from .models import MedalGrant
from .services import _flush_player_states, refresh_player_medals, replace_pins
from .test_state_cache import MedalStateFixture


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'medal-cache-concurrency'}})
class MedalCacheConcurrencyTests(MedalStateFixture, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_cold_cache_fill_holds_player_lock_until_publication(self):
        self.make_video(timems=19000, upload_time=self.earlier)
        refresh_player_medals(self.user.id, full=True)
        grant = MedalGrant.objects.get(user=self.user, definition_code='ability.time.b', revoked_at__isnull=True)
        replace_pins(self.user, [grant.id])
        faster = self.make_video(timems=14000, upload_time=self.later)
        filling, release, attempted, finished = Event(), Event(), Event(), Event()

        def publish(payloads):
            if not filling.is_set():
                filling.set()
                if not release.wait(5):
                    raise AssertionError('cache fill was not released')
            cache.write_player_states(payloads)

        def observe_lock(execute, sql, params, many, context):
            if 'FOR UPDATE' in sql.upper():
                attempted.set()
            return execute(sql, params, many, context)

        def cold_fill():
            close_old_connections()
            try:
                _flush_player_states([self.user.id])
            finally:
                connection.close()

        def upgrade():
            close_old_connections()
            try:
                with connection.execute_wrapper(observe_lock):
                    refresh_player_medals(self.user.id, video_ids=[faster.id])
                finished.set()
            finally:
                connection.close()

        with patch('medal.services.write_player_states', side_effect=publish), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(cold_fill)
            try:
                self.assertTrue(filling.wait(5))
                second = pool.submit(upgrade)
                self.assertTrue(attempted.wait(5))
                self.assertFalse(finished.wait(0.2), 'upgrade bypassed the cache publisher player lock')
            finally:
                release.set()
            first.result(timeout=10)
            second.result(timeout=10)
        rows = cache.read_player_state(self.user.id)['grants']
        self.assertEqual(next(row for row in rows if row['code'] == 'ability.time.b')['stage'], 15000)
