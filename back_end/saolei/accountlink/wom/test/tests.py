from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from unittest.mock import Mock, patch

from django.test import override_settings, SimpleTestCase, TestCase

from accountlink.api import AccountWoMOut
from accountlink.models import AccountWorldOfMinesweeper
from accountlink.services import update_wom_account
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from ..client import _RequestError, fetch_wom_profile
from ..utils import normalize_wom_profile


def public_profile():
    return json.loads(Path(__file__).with_name('public_profile.json').read_text(encoding='utf-8'))


class WomProfileMappingTests(SimpleTestCase):
    def test_public_sample_preserves_existing_units_and_adds_statistics(self):
        data = normalize_wom_profile(public_profile(), 1783173)
        self.assertEqual(data['b_t_ms'], 1213)
        self.assertEqual(data['i_t_ms'], 9661)
        self.assertEqual(data['e_t_ms'], 35765)
        self.assertEqual([data[f'{level}_ioe'] for level in ('b', 'i', 'e')], [1.83, 1.56, 1.4])
        self.assertEqual(data['last_season'], 78)
        self.assertEqual(data['b_endurance_ms'], 582000)
        self.assertEqual(data['i_endurance_ms'], 2591000)
        self.assertEqual(data['e_endurance_ms'], 13888000)
        self.assertEqual([data[f'{level}_ng_t_ms'] for level in ('b', 'i', 'e')], [1282, 16720, 48877])
        self.assertEqual(data['experience_total'], 21163169)
        self.assertEqual(data['minecoin_total'], 3901062)
        self.assertEqual(data['gem_total'], 22780)
        self.assertEqual(data['arena_coin_total'], 0)
        self.assertEqual(data['game_count'], 111645)
        self.assertEqual(data['win_nf'], 16207)
        self.assertEqual(data['play_time_ms'], 2808349910)
        self.assertEqual(data['arena_play_time_ms'], 65626047)
        self.assertEqual(data['bbbv_total'], 5060476)
        self.assertEqual(data['season_count'], 16)
        self.assertEqual([data[f'{level}_win'] for level in ('b', 'i', 'e')], [12361, 4958, 2553])
        self.assertEqual([data[f'{level}_ng_win'] for level in ('b', 'i', 'e')], [245, 66, 548])

    def test_inventory_and_identity_text_are_never_imported(self):
        profile = public_profile()
        profile['user'].update({'username': 'Unreviewed name', 'country': 'XX'})
        profile['userStat'].update({'coins': 1, 'items': {'16': 2, '1': 3}, 'eq': {'0': '550'}})
        data = normalize_wom_profile(profile, 1783173)
        self.assertTrue({'honour', 'minecoin', 'gem', 'coin', 'arena_ticket', 'equipment', 'part', 'name', 'country', 'items', 'eq'}.isdisjoint(data))

    def test_absent_pb_is_null_and_zero_wins_are_preserved(self):
        profile = public_profile()
        profile['timeResults'].pop('12')
        profile['effResults'] = {}
        profile['userStat']['winsNf'] = 0
        data = normalize_wom_profile(profile, 1783173)
        self.assertIsNone(data['i_ng_t_ms'])
        self.assertIsNone(data['b_ioe'])
        self.assertEqual(data['win_nf'], 0)

    def test_missing_statistics_do_not_clear_previous_values(self):
        profile = {'user': {'id': 1}, 'userStat': None, 'noUserStatExp': 42}
        self.assertEqual(normalize_wom_profile(profile, 1), {'experience': 42})
        profile['noUserStatExp'] = -1
        with self.assertRaises(ValueError):
            normalize_wom_profile(profile, 1)
        partial = {'user': {'id': 1}, 'userStat': {'winsAll': 0}}
        self.assertEqual(normalize_wom_profile(partial, 1), {'win': 0})

    def test_narrowed_counter_limits_are_checked_before_saving(self):
        for key, value in [('games', 2 ** 32), ('bbbvAll', 2 ** 32), ('expAll', 2 ** 32), ('coinsAll', 2 ** 32), ('gemsAll', 2 ** 32), ('arenaCoinsAll', 2 ** 32), ('winsNf', 2 ** 32), ('wins1', 2 ** 32), ('seasons', 2 ** 16), ('timeAll', 2 ** 63), ('arenaDuration', 2 ** 63)]:
            profile = public_profile()
            profile['userStat'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                normalize_wom_profile(profile, 1783173)

    def test_malformed_identity_records_or_counters_are_rejected(self):
        original = public_profile()
        for key, value in [('games', True), ('games', 1.5), ('games', -1), ('end1', 86400001), ('lastSeason', 20000)]:
            profile = deepcopy(original)
            profile['userStat'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                normalize_wom_profile(profile, 1783173)
        for user_id in (True, '1783173', 1):
            profile = deepcopy(original)
            profile['user']['id'] = user_id
            with self.subTest(user_id=user_id), self.assertRaises(ValueError):
                normalize_wom_profile(profile, 1783173)
        for records in ([], {'1': {}}):
            profile = deepcopy(original)
            profile['timeResults'] = records
            with self.subTest(records=records), self.assertRaises(ValueError):
                normalize_wom_profile(profile, 1783173)


@override_settings(WOM_API_BASE_URL='https://api.test', WOM_API_TOKEN='test-token', WOM_API_TIMEOUT=6)
class WomHttpClientTests(SimpleTestCase):
    def reply(self, status=200, payload=None, headers=None, raw=None):
        body = raw if raw is not None else json.dumps(public_profile() if payload is None else payload).encode()
        return status, {'content-type': 'application/json', **(headers or {})}, body

    def test_request_uses_token_and_normalizes(self):
        with patch('accountlink.wom.client._request', return_value=self.reply()) as request:
            data = fetch_wom_profile(1783173)
        args = request.call_args.args
        self.assertEqual(args[0], 'https://api.test/profile/1783173')
        self.assertEqual(args[1], {'X-Api-Token': 'test-token'})
        self.assertEqual(args[2], 6)
        self.assertEqual(data['b_t_ms'], 1213)
        self.assertEqual(data['e_ng_t_ms'], 48877)

    @override_settings(WOM_API_TOKEN='')
    def test_missing_token_fails_without_request(self):
        with patch('accountlink.wom.client._request') as request:
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(1783173)
        request.assert_not_called()
        self.assertEqual(context.exception.category, 'requestexception')

    def test_unauthorized_is_not_retried(self):
        with patch('accountlink.wom.client._request', return_value=self.reply(401, {'error': 'unauthorized'})) as request:
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(1783173)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(context.exception.category, 'requestexception')

    def test_rate_limit_retries_after_retry_after(self):
        replies = [self.reply(429, headers={'retry-after': '1'}), self.reply()]
        with patch('accountlink.wom.client._request', side_effect=replies) as request, patch('accountlink.wom.client.time.sleep') as sleep:
            data = fetch_wom_profile(1783173)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1.0)
        self.assertEqual(data['b_t_ms'], 1213)

    def test_protocol_error_is_not_retried(self):
        with patch('accountlink.wom.client._request', return_value=self.reply(502, {'error': 'protocol'})) as request:
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(1783173)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(context.exception.category, 'requestexception')

    def test_connection_error_is_retried_then_mapped(self):
        with patch('accountlink.wom.client._request', return_value=self.reply(502, {'error': 'connection'})) as request, patch('accountlink.wom.client.time.sleep'):
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(1783173)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(context.exception.category, 'requestexception')

    def test_timeout_sources_map_to_timeout(self):
        # 传输层超时、504、502 timeout 三种来源都归为 timeout，且都会重试一次。
        for source, outcome in [
            ('transport', _RequestError('timeout')),
            ('504', self.reply(504, {'error': 'timeout'})),
            ('502 timeout', self.reply(502, {'error': 'timeout'})),
        ]:
            with self.subTest(source=source), patch('accountlink.wom.client._request', side_effect=[outcome, outcome]) as request, patch('accountlink.wom.client.time.sleep'):
                with self.assertRaises(ExceptionToResponse) as context:
                    fetch_wom_profile(1783173)
            self.assertEqual(request.call_count, 2)
            self.assertEqual(context.exception.category, 'timeout')

    def test_total_budget_stops_retry(self):
        # 预算只剩 0.5s，退避需要 1s：不再重试，直接按当前分类失败。
        with patch('accountlink.wom.client._request', return_value=self.reply(429)) as request, \
                patch('accountlink.wom.client.TOTAL_BUDGET', 0.5), \
                patch('accountlink.wom.client.time.sleep') as sleep:
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(1783173)
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(context.exception.category, 'requestexception')

    def test_non_json_response_maps_to_parse_error(self):
        with patch('accountlink.wom.client._request', return_value=self.reply(raw=b'not json')) as request:
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(1783173)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(context.exception.category, 'indexerror')

    def test_identity_mismatch_maps_to_parse_error(self):
        with patch('accountlink.wom.client._request', return_value=self.reply()) as request:
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(1)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(context.exception.category, 'indexerror')


class WomAccountTests(TestCase):
    def setUp(self):
        user = UserProfile.objects.create(username='wom_test', email='wom_test@test.com')
        AccountWorldOfMinesweeper.objects.create(id=1783173, parent=user)

    def test_update_wom(self):
        account = AccountWorldOfMinesweeper.objects.filter(id=1783173).first()
        data = normalize_wom_profile(public_profile(), account.id)
        old_update_time = account.update_time
        with patch('accountlink.services.fetch_wom_profile', new=Mock(return_value=data)):
            update_wom_account(account)
        account = AccountWorldOfMinesweeper.objects.filter(id=1783173).first()
        self.assertEqual(account.id, 1783173)
        self.assertEqual(account.trophy, 1130)
        self.assertEqual(account.experience, 21135733)
        self.assertEqual(account.arena_point, 80)
        self.assertEqual(account.max_difficulty, 188752)
        self.assertEqual(account.win, 36565)
        self.assertEqual(account.last_season, 78)
        self.assertEqual(account.b_t_ms, 1213)
        self.assertEqual(account.i_t_ms, 9661)
        self.assertEqual(account.e_t_ms, 35765)
        self.assertEqual(account.b_ioe, 1.83)
        self.assertEqual(account.i_ioe, 1.56)
        self.assertEqual(account.e_ioe, 1.4)
        self.assertEqual(account.b_mastery, 99)
        self.assertEqual(account.i_mastery, 84)
        self.assertEqual(account.e_mastery, 45)
        self.assertEqual(account.b_winstreak, 92)
        self.assertEqual(account.i_winstreak, 21)
        self.assertEqual(account.e_winstreak, 7)
        self.assertEqual(account.b_endurance_ms, 582000)
        self.assertEqual(account.e_ng_t_ms, 48877)
        self.assertGreater(account.update_time, old_update_time)
        output = AccountWoMOut.from_orm(account).model_dump()
        self.assertEqual(output['e_ng_t_ms'], 48877)
        self.assertEqual(output['minecoin_total'], 3901062)
        self.assertTrue({'honour', 'minecoin', 'gem', 'coin', 'arena_ticket', 'equipment', 'part'}.isdisjoint(output))

    def test_wom_endurance_defaults_and_empty_api_records(self):
        account = AccountWorldOfMinesweeper.objects.get(id=1783173)
        endurance_fields = ['b_endurance_ms', 'i_endurance_ms', 'e_endurance_ms']
        self.assertEqual([getattr(account, field) for field in endurance_fields], [86400000] * 3)
        for field in endurance_fields:
            self.assertFalse(AccountWorldOfMinesweeper._meta.get_field(field).null)
            self.assertEqual(AccountWoMOut.model_json_schema()['properties'][field]['type'], 'integer')
        profile = public_profile()
        profile['userStat'].update({'end1': 0, 'end2': None, 'end3': 0})
        data = normalize_wom_profile(profile, account.id)
        with patch('accountlink.services.fetch_wom_profile', new=Mock(return_value=data)):
            update_wom_account(account)
        account.refresh_from_db()
        output = AccountWoMOut.from_orm(account).model_dump()
        self.assertEqual([output[field] for field in endurance_fields], [86400000] * 3)

    def test_update_wom_counter_ranges(self):
        account = AccountWorldOfMinesweeper.objects.get(id=1783173)
        profile = public_profile()
        profile['userStat'].update({'coinsAll': 2 ** 32 - 1, 'bbbvAll': 2 ** 32 - 1, 'seasons': 2 ** 16 - 1, 'timeAll': 2 ** 40, 'arenaDuration': 2 ** 39})
        data = normalize_wom_profile(profile, account.id)
        with patch('accountlink.services.fetch_wom_profile', new=Mock(return_value=data)):
            update_wom_account(account)
        account.refresh_from_db()
        self.assertEqual(account.minecoin_total, 2 ** 32 - 1)
        self.assertEqual(account.bbbv_total, 2 ** 32 - 1)
        self.assertEqual(account.season_count, 2 ** 16 - 1)
        self.assertEqual(account.play_time_ms, 2 ** 40)
        self.assertEqual(account.arena_play_time_ms, 2 ** 39)

    def test_update_wom_failure_keeps_existing_data(self):
        account = AccountWorldOfMinesweeper.objects.filter(id=1783173).first()
        account.trophy = 123
        account.save(update_fields=['trophy'])
        old_update_time = account.update_time
        error = ExceptionToResponse(obj='import', category='timeout')
        with patch('accountlink.services.fetch_wom_profile', new=Mock(side_effect=error)):
            with self.assertRaises(ExceptionToResponse):
                update_wom_account(account)
        account.refresh_from_db()
        self.assertEqual(account.trophy, 123)
        self.assertEqual(account.update_time, old_update_time)


class WomSlowServerHandler(BaseHTTPRequestHandler):
    """按 user_id 模拟三种坏上游：2 每 0.2 秒吐一块 body，3 发一半停住，4 每 0.2 秒吐一行响应头。"""

    def log_message(self, *args):
        pass

    def _dribble_headers(self):
        try:
            self.wfile.write(b'HTTP/1.1 200 OK\r\n')
            self.wfile.flush()
            for index in range(100):
                self.wfile.write(f'X-Slow-{index}: 1\r\n'.encode())
                self.wfile.flush()
                time.sleep(0.2)
        except OSError:
            pass
        finally:
            self.close_connection = True

    def do_GET(self):
        user_id = int(self.path.rsplit('/', 1)[-1])
        if user_id == 4:
            self._dribble_headers()
            return
        data = json.dumps(public_profile()).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data) * 1000 if user_id == 2 else len(data)))
        self.end_headers()
        try:
            if user_id == 2:
                for _ in range(1000):
                    self.wfile.write(data[:64])
                    self.wfile.flush()
                    time.sleep(0.2)
            else:
                self.wfile.write(data[:10])
                self.wfile.flush()
                time.sleep(5)
        except OSError:
            pass
        finally:
            self.close_connection = True


class WomSlowServerTests(SimpleTestCase):
    """真实 HTTP 用例：只有走真实 socket 才能验证超时语义与看门狗能否打断阻塞读。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), WomSlowServerHandler)
        cls.base_url = f'http://127.0.0.1:{cls.server.server_address[1]}'
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def test_trickling_headers_abort_at_total_budget(self):
        # 响应头每 0.2 秒一行：单次读超时拦不住，必须靠看门狗。
        with self.settings(WOM_API_BASE_URL=self.base_url, WOM_API_TOKEN='test-token', WOM_API_TIMEOUT=0.5), \
                patch('accountlink.wom.client.TOTAL_BUDGET', 1.0):
            started = time.monotonic()
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(4)
            elapsed = time.monotonic() - started
        self.assertEqual(context.exception.category, 'timeout')
        self.assertLess(elapsed, 3.0)

    def test_trickling_body_aborts_at_total_budget(self):
        # 上游每 0.2 秒吐一块，单次读不会超时；只有总预算能中止它。
        with self.settings(WOM_API_BASE_URL=self.base_url, WOM_API_TOKEN='test-token', WOM_API_TIMEOUT=0.5), \
                patch('accountlink.wom.client.TOTAL_BUDGET', 1.0):
            started = time.monotonic()
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(2)
            elapsed = time.monotonic() - started
        self.assertEqual(context.exception.category, 'timeout')
        self.assertLess(elapsed, 3.0)

    def test_body_read_timeout_maps_to_timeout(self):
        # 发完响应头和部分 body 后停住：socket 读超时，应归为 timeout。
        with self.settings(WOM_API_BASE_URL=self.base_url, WOM_API_TOKEN='test-token', WOM_API_TIMEOUT=0.5):
            with self.assertRaises(ExceptionToResponse) as context:
                fetch_wom_profile(3)
        self.assertEqual(context.exception.category, 'timeout')
