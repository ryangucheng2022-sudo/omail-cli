#!/usr/bin/env python3
"""Unit tests for omail (stdlib unittest, fully offline).

Run:  python3 -m unittest discover -s tests -v
The module under test is ../bin/omail relative to this file.
"""
import contextlib
import importlib.machinery
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
OMAIL = os.path.join(HERE, '..', 'bin', 'omail')


def load_module():
    loader = importlib.machinery.SourceFileLoader('omail_t', OMAIL)
    spec = importlib.util.spec_from_loader('omail_t', loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def capture(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **kw)
    return buf.getvalue()


class TestParseRest(unittest.TestCase):
    def setUp(self):
        self.m = load_module()

    def test_pairs_flags_positionals(self):
        pos, args = self.m.parse_rest(
            ['ID1', '--subject', 'Hi there', '--dry-run', '--top', '5'])
        self.assertEqual(pos, ['ID1'])
        self.assertEqual(args['subject'], 'Hi there')
        self.assertIs(args['dry_run'], True)
        self.assertEqual(args['top'], '5')

    def test_dashed_key_normalised(self):
        _, args = self.m.parse_rest(['--body-file', '/tmp/x'])
        self.assertEqual(args['body_file'], '/tmp/x')


class TestProxyEnv(unittest.TestCase):
    def _probe(self, extra_env, drop):
        env = {k: v for k, v in os.environ.items() if k not in drop}
        env.update(extra_env)
        code = (
            "import importlib.machinery;"
            "m = importlib.machinery.SourceFileLoader('b', %r).load_module();"
            "print('HOST' if m._pu.hostname else 'NONE')" % OMAIL)
        out = subprocess.run([sys.executable, '-c', code], env=env,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_uppercase_only_recognised(self):
        r = self._probe({'HTTPS_PROXY': 'http://proxy.local:8080'},
                        drop={'https_proxy', 'http_proxy', 'HTTP_PROXY'})
        self.assertEqual(r, 'HOST')

    def test_lowercase_recognised(self):
        r = self._probe({'https_proxy': 'http://proxy.local:8080'},
                        drop={'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY'})
        self.assertEqual(r, 'HOST')

    def test_no_proxy_means_direct(self):
        r = self._probe({}, drop={'https_proxy', 'HTTPS_PROXY',
                                  'http_proxy', 'HTTP_PROXY'})
        self.assertEqual(r, 'NONE')


class TestTenantDiscovery(unittest.TestCase):
    def setUp(self):
        self.m = load_module()

    def _issuer(self, issuer):
        payload = json.dumps({'issuer': issuer}).encode()
        with mock.patch.object(self.m, 'https',
                               return_value=(200, payload)):
            return self.m.discover_tenant('login.example.com', 'acme.com')

    def test_issuer_with_v2_suffix(self):
        self.assertEqual(
            self._issuer('https://login.example.com/GUID-123/v2.0'),
            'GUID-123')

    def test_issuer_without_suffix(self):
        self.assertEqual(
            self._issuer('https://login.example.com/GUID-123'), 'GUID-123')


class TestPagination(unittest.TestCase):
    def setUp(self):
        self.m = load_module()
        self.pages = {
            '/api/v2.0/things?$top=2': {
                'value': [1, 2],
                '@odata.nextLink': 'https://partner.outlook.cn'
                                   '/api/v2.0/things?$skiptoken=abc'},
            '/api/v2.0/things?$skiptoken=abc': {
                'value': [3, 4],
                '@odata.nextLink': 'https://partner.outlook.cn'
                                   '/api/v2.0/things?$skiptoken=def'},
            '/api/v2.0/things?$skiptoken=def': {'value': [5]},
        }

    def fake_api_json(self, method, path, token, body=None, headers=None,
                      safe_retry=None):
        self.assertEqual(method, 'GET')
        return self.pages[path]

    def test_follows_nextlink_to_end(self):
        with mock.patch.object(self.m, 'api_json', self.fake_api_json):
            got = self.m.api_paged('/api/v2.0/things?$top=2', 'tok')
        self.assertEqual(got, [1, 2, 3, 4, 5])

    def test_limit_stops_early(self):
        with mock.patch.object(self.m, 'api_json', self.fake_api_json):
            got = self.m.api_paged('/api/v2.0/things?$top=2', 'tok',
                                   limit=3)
        self.assertEqual(got, [1, 2, 3])


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.m = load_module()

    def test_check_emails_ok_and_bad(self):
        self.assertEqual(self.m.check_emails('a@b.com, c@d.com', '--to'),
                         ['a@b.com', 'c@d.com'])
        with self.assertRaises(SystemExit) as cm:
            self.m.check_emails('not-an-email', '--to')
        self.assertEqual(cm.exception.code, 64)

    def test_require_missing(self):
        with self.assertRaises(SystemExit) as cm:
            self.m.require({'to': 'a@b.com'}, 'to', 'subject')
        self.assertEqual(cm.exception.code, 64)

    def test_parse_iso_bad(self):
        with self.assertRaises(SystemExit):
            self.m.parse_iso('next friday', '--start')

    def test_build_message_missing_subject(self):
        with self.assertRaises(SystemExit):
            self.m.build_message({'to': 'a@b.com', 'body': 'x'})

    def test_build_message_missing_attachment(self):
        with self.assertRaises(SystemExit):
            self.m.build_message({'to': 'a@b.com', 'subject': 's',
                                  'body': 'x', 'attach': '/no/such/file'})

    def test_build_event_end_before_start(self):
        with self.assertRaises(SystemExit):
            self.m.build_event({'subject': 's',
                                'start': '2026-11-06T11:00:00',
                                'end': '2026-11-06T10:00:00'})

    def test_build_event_ok(self):
        ev = self.m.build_event({'subject': 's',
                                 'start': '2026-11-06T10:00:00',
                                 'end': '2026-11-06T11:00:00',
                                 'attendees': 'a@b.com'})
        self.assertEqual(ev['Start']['TimeZone'], 'China Standard Time')
        self.assertEqual(ev['Attendees'][0]['EmailAddress']['Address'],
                         'a@b.com')


class TestDryRun(unittest.TestCase):
    def setUp(self):
        self.m = load_module()

    def _no_api(self, *a, **kw):
        raise AssertionError('API must not be called in dry-run')

    def test_send_dry_run(self):
        with mock.patch.object(self.m, 'api', self._no_api):
            out = capture(self.m.cmd_send, None,
                          {'to': 'a@b.com', 'subject': 's', 'body': 'hello',
                           'dry_run': True})
        d = json.loads(out)
        self.assertTrue(d['dry_run'])
        self.assertEqual(d['action'], 'send')
        self.assertEqual(d['detail']['body_chars'], 5)

    def test_event_create_dry_run(self):
        with mock.patch.object(self.m, 'api_json', self._no_api):
            out = capture(self.m.cmd_event_create, None,
                          {'subject': 's', 'start': '2026-11-06T10:00:00',
                           'end': '2026-11-06T11:00:00', 'dry_run': True})
        d = json.loads(out)
        self.assertTrue(d['dry_run'])
        self.assertEqual(d['detail']['event']['Subject'], 's')


class TestMarkGuard(unittest.TestCase):
    def setUp(self):
        self.m = load_module()

    def _run_main(self, argv):
        with mock.patch.object(self.m, 'access_token', lambda: 'tok'), \
                mock.patch.object(sys, 'argv', argv):
            return self.m.main()

    def test_no_flag_is_usage_error(self):
        with self.assertRaises(SystemExit) as cm:
            self._run_main(['omail', 'mark', 'MID'])
        self.assertEqual(cm.exception.code, 64)

    def test_both_flags_is_usage_error(self):
        with self.assertRaises(SystemExit) as cm:
            self._run_main(['omail', 'mark', 'MID', '--read', '--unread'])
        self.assertEqual(cm.exception.code, 64)

    def test_missing_id_is_usage_error(self):
        with self.assertRaises(SystemExit) as cm:
            self._run_main(['omail', 'read'])
        self.assertEqual(cm.exception.code, 64)


class TestJournal(unittest.TestCase):
    def setUp(self):
        self.m = load_module()
        self.tmp = tempfile.mkdtemp()
        self.m.STORE = os.path.join(self.tmp, 'token_store.json')
        self.payload = {'to': 'a@b.com', 'subject': 's'}

    def test_inflight_then_done_then_expire_by_force(self):
        key = self.m.journal_guard('send', self.payload)
        with self.assertRaises(SystemExit):  # identical, still in-flight
            self.m.journal_guard('send', self.payload)
        self.m.journal_done(key)
        with self.assertRaises(SystemExit):  # identical, just completed
            self.m.journal_guard('send', self.payload)
        key2 = self.m.journal_guard('send', self.payload, force=True)
        self.assertTrue(key2)
        other = self.m.journal_guard('send', {'to': 'x@y.com'})
        self.assertNotEqual(other, key2)


class TestSendIdempotency(unittest.TestCase):
    def setUp(self):
        self.m = load_module()
        self.tmp = tempfile.mkdtemp()
        self.m.STORE = os.path.join(self.tmp, 'token_store.json')
        self.calls = []

    def fake_api(self, method, path, token, body=None, headers=None,
                 safe_retry=None):
        self.calls.append((method, path))
        return 202, b''

    def test_duplicate_send_blocked(self):
        args = {'to': 'a@b.com', 'subject': 's', 'body': 'hello'}
        with mock.patch.object(self.m, 'api', self.fake_api):
            capture(self.m.cmd_send, 'tok', dict(args))
            self.assertEqual(len(self.calls), 1)
            with self.assertRaises(SystemExit):
                capture(self.m.cmd_send, 'tok', dict(args))
            self.assertEqual(len(self.calls), 1)  # never hit the API twice
            capture(self.m.cmd_send, 'tok', dict(args, force=True))
            self.assertEqual(len(self.calls), 2)


class FakeConn:
    mode = 'connect_fail'
    built = 0

    def __init__(self, *a, **kw):
        FakeConn.built += 1
        if FakeConn.mode == 'connect_fail':
            raise OSError('cannot connect')

    def set_tunnel(self, *a, **kw):
        pass

    def request(self, *a, **kw):
        raise ConnectionResetError('response lost after sending')

    def getresponse(self):  # pragma: no cover - request raises first
        raise AssertionError

    def close(self):
        pass


class TestRetryPolicy(unittest.TestCase):
    def setUp(self):
        self.m = load_module()
        FakeConn.built = 0

    def _call(self, safe_retry):
        with mock.patch.object(self.m.http.client, 'HTTPSConnection',
                               FakeConn), \
                mock.patch('time.sleep', lambda s: None):
            return self.m.https('example.com', 'POST', '/x', {},
                                safe_retry=safe_retry)

    def test_connect_failure_retried_for_writes(self):
        FakeConn.mode = 'connect_fail'
        with self.assertRaises(OSError):
            self._call(safe_retry=False)
        self.assertEqual(FakeConn.built, 5)  # all attempts used

    def test_sent_failure_not_retried_for_writes(self):
        FakeConn.mode = 'sent_fail'
        with self.assertRaises(self.m.AmbiguousError):
            self._call(safe_retry=False)
        self.assertEqual(FakeConn.built, 1)  # no blind retry

    def test_sent_failure_retried_for_reads(self):
        FakeConn.mode = 'sent_fail'
        with self.assertRaises(ConnectionResetError):
            self._call(safe_retry=True)
        self.assertEqual(FakeConn.built, 5)


class TestBodyMax(unittest.TestCase):
    def setUp(self):
        self.m = load_module()
        self.msg = {
            'Id': 'x', 'Subject': 's', 'From': {}, 'ToRecipients': [],
            'CcRecipients': [], 'ReceivedDateTime': '2026-11-04T00:00:00Z',
            'IsRead': True, 'HasAttachments': False,
            'Body': {'ContentType': 'Text', 'Content': 'A' * 100},
        }

    def fake_api_json(self, method, path, token, body=None, headers=None,
                      safe_retry=None):
        return self.msg

    def test_truncation_flag(self):
        with mock.patch.object(self.m, 'api_json', self.fake_api_json):
            out = capture(self.m.cmd_read, 'tok',
                          {'id': 'x', 'body_max': '10'})
        d = json.loads(out)
        self.assertEqual(len(d['body_text']), 10)
        self.assertTrue(d['body_truncated'])

    def test_no_truncation_by_default(self):
        with mock.patch.object(self.m, 'api_json', self.fake_api_json):
            out = capture(self.m.cmd_read, 'tok', {'id': 'x'})
        d = json.loads(out)
        self.assertEqual(len(d['body_text']), 100)
        self.assertFalse(d['body_truncated'])


if __name__ == '__main__':
    unittest.main()
