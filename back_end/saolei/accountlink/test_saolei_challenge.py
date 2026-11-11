from contextlib import nullcontext
from io import StringIO
import json
from unittest.mock import Mock, patch

from django.core.management import call_command, CommandError
from django.test import override_settings, SimpleTestCase, TestCase
from django.utils import timezone
import httpx

from userprofile.models import UserProfile
from .models import AccountLinkQueue, AccountSaolei, Platform, SaoleiApiVideo
from .saolei.challenge import BotChallengeError, solve_bot_challenge
from .saolei.client import ThrottledTransport

CHALLENGE_LOCATION = 'https://saolei.wang/bot/challenge?next=%2Fvideo%2Fdownload%2F7'


def challenge_board(token='t0'):
    return {
        'token': token, 'width': 2, 'height': 2, 'board3bv': 1, 'won': False, 'lost': False, 'moves': 0,
        'cells': [{'state': 0, 'num': None} for _ in range(4)],
    }


def bound_account(remote_id=101, username='challenge_import'):
    user = UserProfile.objects.create_user(username=username, email=f'{username}@example.com')
    account = AccountSaolei.objects.create(pk=remote_id, parent=user)
    AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier=str(remote_id), userprofile=user, verified=True)
    return account


class BotChallengeTransportTests(SimpleTestCase):
    def test_challenge_redirect_is_solved_once_then_replayed_with_cookies(self):
        redis = Mock()
        redis.set.return_value = True
        requests = []

        def respond(request):
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(307, headers={'Location': CHALLENGE_LOCATION})
            return httpx.Response(200, content=b'file')

        challenge = Mock(return_value={'saolei_bot': 'ok'})
        transport = ThrottledTransport(httpx.MockTransport(respond), challenge=challenge)
        with patch('accountlink.saolei.client.get_redis_connection', return_value=redis):
            first = transport.handle_request(httpx.Request('GET', 'https://saolei.wang/video/download/7'))
            second = transport.handle_request(httpx.Request('GET', 'https://saolei.wang/video/download/8'))
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        challenge.assert_called_once_with(CHALLENGE_LOCATION)
        self.assertEqual(len(requests), 3)
        self.assertIn('saolei_bot=ok', requests[1].headers['Cookie'])
        self.assertIn('saolei_bot=ok', requests[2].headers['Cookie'])

    def test_httpx_client_gets_the_replayed_download_body(self):
        redis = Mock()
        redis.set.return_value = True
        requests = []

        def respond(request):
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(307, headers={'Location': CHALLENGE_LOCATION})
            return httpx.Response(200, content=b'file', headers={'Content-Disposition': 'attachment; filename="7.evf"'})

        challenge = Mock(return_value={'saolei_bot': 'ok'})
        transport = ThrottledTransport(httpx.MockTransport(respond), challenge=challenge)
        with patch('accountlink.saolei.client.get_redis_connection', return_value=redis):
            with httpx.Client(transport=transport, follow_redirects=False) as client:
                response = client.get('https://saolei.wang/video/download/7')
        self.assertEqual((response.status_code, response.content), (200, b'file'))
        self.assertEqual(response.headers['Content-Disposition'], 'attachment; filename="7.evf"')
        challenge.assert_called_once_with(CHALLENGE_LOCATION)

    def test_challenge_redirect_without_handler_is_left_untouched(self):
        redis = Mock()
        redis.set.return_value = True
        transport = ThrottledTransport(httpx.MockTransport(lambda request: httpx.Response(307, headers={'Location': CHALLENGE_LOCATION})))
        with patch('accountlink.saolei.client.get_redis_connection', return_value=redis):
            response = transport.handle_request(httpx.Request('GET', 'https://saolei.wang/video/download/7'))
        self.assertEqual(response.status_code, 307)

    def test_unrelated_redirect_never_starts_a_challenge(self):
        redis = Mock()
        redis.set.return_value = True
        challenge = Mock()
        transport = ThrottledTransport(httpx.MockTransport(lambda request: httpx.Response(307, headers={'Location': 'https://saolei.wang/other'})), challenge=challenge)
        with patch('accountlink.saolei.client.get_redis_connection', return_value=redis):
            response = transport.handle_request(httpx.Request('GET', 'https://saolei.wang/video/download/7'))
        self.assertEqual(response.status_code, 307)
        challenge.assert_not_called()


class BotChallengeInteractionTests(SimpleTestCase):
    def test_human_move_is_submitted_and_session_cookies_are_returned(self):
        requests = []

        def respond(request):
            requests.append(request)
            if request.method == 'POST':
                return httpx.Response(200, json=challenge_board(), headers={'Set-Cookie': 'saolei_bot=ok; path=/'})
            return httpx.Response(200, json={'token': 't1', 'won': True, 'lost': False, 'moves': 1, 'diff': [{'i': 0, 's': 1, 'n': 2}], 'mineCell': -1})

        client = httpx.Client(base_url='https://saolei.wang', transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        lines = iter(['1 1'])
        output = []
        cookies = solve_bot_challenge(CHALLENGE_LOCATION, read_line=lambda: next(lines), write=output.append, client=client)
        self.assertEqual(cookies['saolei_bot'], 'ok')
        self.assertTrue(any('#' in line for line in output))
        self.assertTrue(any('验证成功' in line for line in output))
        submitted = json.loads(next(request.content for request in requests if request.method == 'PUT'))
        self.assertEqual((submitted['token'], submitted['action'], submitted['cell'], submitted['base']), ('t0', 'open', 0, '0000'))

    def test_flag_action_is_accepted(self):
        requests = []

        def respond(request):
            requests.append(request)
            if request.method == 'POST':
                return httpx.Response(200, json=challenge_board())
            return httpx.Response(200, json={'token': 't1', 'won': True, 'lost': False, 'moves': 1, 'diff': [{'i': 3, 's': 2, 'n': None}]})

        client = httpx.Client(base_url='https://saolei.wang', transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        lines = iter(['2 2 f'])
        solve_bot_challenge(CHALLENGE_LOCATION, read_line=lambda: next(lines), write=lambda text: None, client=client)
        submitted = json.loads(next(request.content for request in requests if request.method == 'PUT'))
        self.assertEqual((submitted['action'], submitted['cell']), ('flag', 3))

    def test_foreign_redirect_is_rejected_without_any_request(self):
        with self.assertRaises(BotChallengeError):
            solve_bot_challenge('https://elsewhere.example/bot/challenge', read_line=lambda: '', write=lambda text: None)

    def test_missing_terminal_input_stops_the_challenge(self):
        client = httpx.Client(base_url='https://saolei.wang', transport=httpx.MockTransport(lambda request: httpx.Response(200, json=challenge_board())))
        self.addCleanup(client.close)
        with self.assertRaisesMessage(BotChallengeError, '没有交互输入'):
            solve_bot_challenge(CHALLENGE_LOCATION, read_line=lambda: '', write=lambda text: None, client=client)

    def test_invalid_input_is_reported_and_the_same_board_is_shown_again(self):
        client = httpx.Client(base_url='https://saolei.wang', transport=httpx.MockTransport(lambda request: httpx.Response(200, json=challenge_board())))
        self.addCleanup(client.close)
        lines = iter(['9 9', 'q'])
        output = []
        with self.assertRaisesMessage(BotChallengeError, '已取消验证'):
            solve_bot_challenge(CHALLENGE_LOCATION, read_line=lambda: next(lines), write=output.append, client=client)
        self.assertTrue(any('输入无效' in line for line in output))


@override_settings(BAIDU_VERIFY_SKIP=True)
class BotChallengeCommandTests(TestCase):
    def test_failed_verification_stops_the_command_without_retrying_sources(self):
        account = bound_account()
        for remote_id in (1, 2):
            SaoleiApiVideo.objects.create(remote_id=remote_id, user=account, upload_time=timezone.now(), level='b', software='Arbiter', status=20)
        client = Mock()
        client.download_videos.side_effect = BotChallengeError('已取消验证')
        with patch('accountlink.management.commands.sync_saolei_api.saolei_client', return_value=nullcontext(client)):
            with self.assertRaisesMessage(CommandError, '上游真人验证未完成'):
                call_command('sync_saolei_api', account_id=[101], phase='videos', stdout=StringIO(), stderr=StringIO())
        self.assertEqual(client.download_videos.call_count, 1)
