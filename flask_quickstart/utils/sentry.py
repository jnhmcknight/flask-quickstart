"""
application.utils.sentry

Sentry utilities
"""

import json
import logging
import os
import urllib

try:
    import sentry_sdk

    from sentry_sdk.integrations.boto3 import Boto3Integration
    from sentry_sdk.integrations.flask import FlaskIntegration
    SENTRY_IMPORT_ERROR = None
except ImportError as exc:
    SENTRY_IMPORT_ERROR = exc


# Keys to values we wish to redact before sending to Sentry.
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "client_secret",
        "shadow",
        "access_token",
        "refresh_token",
    }
)

SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
    }
)


# pylint: disable=unused-argument
def strip_sensitive_data(event, hint):
    """
    Strip sensitive values from Sentry events before sending them out.

    This may not be exhaustive; regular auditing of data sent
    to Sentry is required.
    """

    # Handle URL query strings that might include a secret
    if "request" in event and event["request"].get("query_string"):
        query_string = urllib.parse.parse_qs(event["request"]["query_string"])
        for key, _ in query_string.items():
            if key.lower() in SENSITIVE_KEYS:
                query_string[key] = "REDACTED"

        event["request"]["query_string"] = urllib.parse.urlencode(
            query_string, doseq=True
        )

    # # Handle Headers that might include a secret (e.g. any Authorization header)
    if "request" in event and event["request"].get("headers"):
        for header_name, _ in event["request"]["headers"].items():
            if header_name.lower() in SENSITIVE_HEADERS:
                event["request"]["headers"][header_name] = "REDACTED"

    # # Handle request body data
    if "request" in event and event["request"].get("data"):
        for key, _ in event["request"]["data"].items():
            if key.lower() in SENSITIVE_KEYS:
                event["request"]["data"][key] = "REDACTED"

    return event


def setup_sentry(config=None, *, dsn=None, **kwargs):

    if SENTRY_IMPORT_ERROR is not None:
        logging.warning('Sentry cannot be instantiated, it failed to import in this virtual environment:')
        logging.exception(SENTRY_IMPORT_ERROR)
        return

    if config.get('ENV', '').lower() in ("development", "testing"):
        print("[WARNING] Not setting up Sentry due to environment")
        return

    if dsn is None:
        dsn = config.get(
            'SENTRY_DSN',
            os.environ.get(
                'SENTRY_DSN',
                os.environ.get('FLASK_SENTRY_DSN')
            )
        )

    # Using this as a truthy value, since we don't want to allow "", None or False as DSNs
    if not dsn:
        print("[WARNING] Cannot setup Sentry. No DSN found")
        return

    if 'transport' not in kwargs or not kwargs['transport']:
        # This isn't actually a syntax error, because `print` is a function in py3 and not a
        # statement.
        kwargs['transport'] = (
            sentry_sdk.transport.HttpTransport if kwargs.get('debug') is not True else print
        )

    if 'environment' not in kwargs:
        kwargs['environment'] = config.get('ENV')

    if 'request_bodies' not in kwargs:
        kwargs['request_bodies'] = "always"

    if 'integrations' not in kwargs or not kwargs['integrations']:
        kwargs['integrations'] = []
    elif not isinstance(kwargs['integrations'], list):
        kwargs['integrations'] = [kwargs['integrations']]

    add_boto3_int = True
    add_flask_int = True
    for integration in kwargs['integrations']:
        if isinstance(integration, Boto3Integration):
            add_boto3_int = False
        elif isinstance(integration, FlaskIntegration):
            add_flask_int = False

    if add_boto3_int:
        kwargs['integrations'].append(Boto3Integration())
    if add_flask_int:
        kwargs['integrations'].append(FlaskIntegration())

    sentry_sdk.init(dsn=dsn, **kwargs)
