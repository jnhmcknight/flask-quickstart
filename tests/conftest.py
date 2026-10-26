"""
tests.conftest
"""

import json
import os

import pytest

from flask_quickstart import create_app


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure that settings from the surrounding shell don't leak into the app config"""

    for key in list(os.environ):
        if key.startswith(('FLASK_', 'SENTRY_')) or key == 'ENV_FOR_DYNACONF':
            monkeypatch.delenv(key)

    monkeypatch.setenv('FLASK_ENV', 'testing')


@pytest.fixture()
def make_app(monkeypatch):
    """
    Returns a function that builds an app via `create_app`, with the given config values
    provided the same way a deployed app gets them: as `FLASK_*` env vars loaded by Dynaconf.
    """

    def _make_app(name='testing', **config):
        for key, value in config.items():
            monkeypatch.setenv(f'FLASK_{key}', value if isinstance(value, str) else json.dumps(value))
        return create_app(name)

    return _make_app


@pytest.fixture()
def app(make_app):
    """A Flask app with only the default configuration"""

    return make_app()
