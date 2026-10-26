"""
tests.test_sentry
"""

import json

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.integrations.boto3 import Boto3Integration
from sentry_sdk.integrations.flask import FlaskIntegration

from flask_quickstart.utils import sentry, zappa


DSN = 'https://key@o0.ingest.sentry.io/1'


@pytest.fixture()
def sentry_init(monkeypatch):
    """Records calls to `sentry_sdk.init` instead of initializing Sentry"""

    calls = []
    monkeypatch.setattr(sentry.sentry_sdk, 'init', lambda **kwargs: calls.append(kwargs))
    return calls


def test_strip_sensitive_data():
    event = {
        'request': {
            'query_string': 'password=hunter2&page=2',
            'headers': {'Authorization': 'Bearer secret', 'Accept': 'text/html'},
            'data': {'client_secret': 'secret', 'name': 'value'},
        },
    }

    event = sentry.strip_sensitive_data(event, None)

    assert event['request']['query_string'] == 'password=REDACTED&page=2'
    assert event['request']['headers'] == {'Authorization': 'REDACTED', 'Accept': 'text/html'}
    assert event['request']['data'] == {'client_secret': 'REDACTED', 'name': 'value'}


def test_strip_sensitive_data_without_request():
    assert sentry.strip_sensitive_data({'message': 'hi'}, None) == {'message': 'hi'}


def test_setup_sentry(sentry_init):
    sentry.setup_sentry({'ENV': 'production'}, dsn=DSN)

    (kwargs,) = sentry_init
    assert kwargs['dsn'] == DSN
    assert kwargs['environment'] == 'production'
    assert kwargs['traces_sample_rate'] == 0.1
    assert 'transport' not in kwargs
    assert [type(i) for i in kwargs['integrations']] == [Boto3Integration, FlaskIntegration]


def test_setup_sentry_dsn_sources(sentry_init, monkeypatch):
    sentry.setup_sentry({'ENV': 'production', 'SENTRY_DSN': DSN})
    monkeypatch.setenv('SENTRY_DSN', DSN)
    sentry.setup_sentry({'ENV': 'production'})
    monkeypatch.delenv('SENTRY_DSN')
    monkeypatch.setenv('FLASK_SENTRY_DSN', DSN)
    sentry.setup_sentry({'ENV': 'production'})

    assert [kwargs['dsn'] for kwargs in sentry_init] == [DSN, DSN, DSN]


def test_setup_sentry_keeps_provided_options(sentry_init):
    flask_integration = FlaskIntegration()
    sentry.setup_sentry(
        {'ENV': 'production'},
        dsn=DSN,
        environment='staging',
        traces_sample_rate=1.0,
        integrations=flask_integration,
    )

    (kwargs,) = sentry_init
    assert kwargs['environment'] == 'staging'
    assert kwargs['traces_sample_rate'] == 1.0
    assert kwargs['integrations'][0] is flask_integration
    assert [type(i) for i in kwargs['integrations']] == [FlaskIntegration, Boto3Integration]


def test_setup_sentry_debug_uses_print_transport(sentry_init):
    sentry.setup_sentry({'ENV': 'production'}, dsn=DSN, debug=True)

    (kwargs,) = sentry_init
    assert kwargs['transport'] is sentry.PrintTransport
    assert kwargs['debug'] is True


@pytest.mark.parametrize('config, dsn', [
    ({'ENV': 'development'}, DSN),
    ({'ENV': 'Testing'}, DSN),
    ({'ENV': 'production'}, None),
    ({'ENV': 'production'}, ''),
    (None, None),
])
def test_setup_sentry_skipped(sentry_init, config, dsn):
    sentry.setup_sentry(config, dsn=dsn)
    assert sentry_init == []


def test_setup_sentry_without_sentry_installed(sentry_init, monkeypatch):
    monkeypatch.setattr(sentry, 'SENTRY_IMPORT_ERROR', ImportError('not installed'))
    sentry.setup_sentry({'ENV': 'production'}, dsn=DSN)
    assert sentry_init == []


def test_print_transport(capsys):
    envelope = Envelope()
    envelope.add_event({'message': 'hello'})

    sentry.PrintTransport().capture_envelope(envelope)

    assert '"message":"hello"' in capsys.readouterr().out.replace(' ', '')


def test_capture_exception(monkeypatch):
    captured = []
    monkeypatch.setattr(sentry.sentry_sdk, 'capture_exception', captured.append)
    exc = ValueError('boom')

    sentry.capture_exception(exc)
    assert captured == [exc]

    monkeypatch.setattr(sentry, 'SENTRY_IMPORT_ERROR', ImportError('not installed'))
    sentry.capture_exception(exc)
    assert captured == [exc]


@pytest.fixture()
def zappa_captures(monkeypatch, tmp_path):
    """Records the exception and scope tags that `zappa_handler` reports to Sentry"""

    captures = []

    def capture_exception(exc):
        scope = sentry_sdk.get_current_scope()
        captures.append((exc, dict(scope._tags), dict(scope._extras)))  # pylint: disable=protected-access

    monkeypatch.setattr(zappa, 'setup_sentry', lambda: None)
    monkeypatch.setattr(zappa.sentry_sdk, 'capture_exception', capture_exception)
    monkeypatch.chdir(tmp_path)
    return captures


def test_zappa_handler(zappa_captures, tmp_path):
    (tmp_path / 'package_info.json').write_text(json.dumps({'build': '42'}))
    exc = ValueError('boom')
    event = {
        'httpMethod': 'GET',
        'path': '/thing',
        'headers': {'Host': 'example.com', 'User-Agent': 'tests'},
        'requestContext': {'stage': 'prod'},
    }

    assert zappa.zappa_handler(exc, event, None) is False

    ((captured, tags, extras),) = zappa_captures
    assert captured is exc
    assert tags == {
        'handler': 'raw-zappa',
        'build': '42',
        'http_method': 'GET',
        'path': '/thing',
        'host': 'example.com',
        'user_agent': 'tests',
        'stage': 'prod',
    }
    assert extras == {'event': event}
    # Tags are only applied to the reported exception, not the surrounding scope
    assert 'handler' not in sentry_sdk.get_current_scope()._tags  # pylint: disable=protected-access


def test_zappa_capture_exception(zappa_captures):
    assert zappa.capture_exception(ValueError('boom'), {}, None) is True
    ((_, tags, _),) = zappa_captures
    assert tags == {'handler': 'raw-zappa'}
