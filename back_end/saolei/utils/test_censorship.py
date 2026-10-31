from unittest.mock import Mock, patch

from django.test import override_settings, SimpleTestCase
from requests.exceptions import Timeout

from utils import verify_text


def response(body):
    result = Mock()
    result.json.return_value = body
    return result


@override_settings(BAIDU_VERIFY_SKIP=False)
class TextCensorshipTests(SimpleTestCase):
    def test_empty_text_does_not_request_moderation(self):
        with patch('utils.requests.request') as request:
            self.assertTrue(verify_text(''))
        request.assert_not_called()

    @override_settings(BAIDU_VERIFY_SKIP=True)
    def test_explicit_test_bypass_is_preserved(self):
        with patch('utils.requests.request') as request:
            self.assertTrue(verify_text('测试'))
        request.assert_not_called()

    def test_only_compliant_text_is_accepted(self):
        for conclusion, allowed in [('合规', True), ('不合规', False), ('疑似', False)]:
            with self.subTest(conclusion=conclusion), patch('utils.get_ACCESS_TOKEN', return_value='test-token'):
                with patch('utils.requests.request', return_value=response({'conclusion': conclusion})) as request:
                    self.assertEqual(verify_text('雷', 12, '203.0.113.7'), allowed)
                request.assert_called_once()
                self.assertEqual(request.call_args.kwargs['data'], {'text': '雷', 'userId': '12', 'userIp': '203.0.113.7'})
                self.assertEqual(request.call_args.kwargs['timeout'], 5)

    def test_missing_or_failed_verdict_raises_instead_of_reporting_a_violation(self):
        for body in ({}, {'conclusion': '审核失败'}, {'error_code': 18, 'error_msg': 'quota exceeded'}):
            with self.subTest(body=body), patch('utils.get_ACCESS_TOKEN', return_value='test-token'):
                with patch('utils.requests.request', return_value=response(body)):
                    with self.assertRaisesMessage(ValueError, 'did not return a verdict'):
                        verify_text('username')

    def test_expired_token_is_refreshed_once(self):
        with patch('utils.get_ACCESS_TOKEN', return_value='old-token'), patch('utils.get_access_token', return_value='new-token') as refresh:
            with patch('utils.requests.request', side_effect=[response({'error_code': 111}), response({'conclusion': '合规'})]) as request:
                self.assertTrue(verify_text('username'))
        refresh.assert_called_once()
        self.assertEqual(request.call_count, 2)
        self.assertTrue(request.call_args.args[1].endswith('access_token=new-token'))
        self.assertEqual(request.call_args.kwargs['timeout'], 5)

    def test_network_timeout_is_not_treated_as_approval(self):
        with patch('utils.get_ACCESS_TOKEN', return_value='test-token'), patch('utils.requests.request', side_effect=Timeout):
            with self.assertRaises(Timeout):
                verify_text('username')
