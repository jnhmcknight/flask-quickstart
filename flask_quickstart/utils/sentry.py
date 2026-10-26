"""
flask_quickstart.utils.sentry

Sentry utilities
"""

import logging
import os
import urllib.parse

try:
    import sentry_sdk
    from sentry_sdk.integrations.boto3 import Boto3Integration
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.transport import Transport

    SENTRY_IMPORT_ERROR = None
except ImportError as exc:
    SENTRY_IMPORT_ERROR = exc
    Transport = object

logger = logging.getLogger(__name__)


class PrintTransport(Transport):
    """Prints envelopes instead of sending them, for use when debugging."""

    def capture_envelope(self, envelope):
        print(envelope.serialize().decode("utf-8", errors="replace"))


def capture_exception(exc):
    """Report an exception to Sentry if it is available, otherwise do nothing."""

    if SENTRY_IMPORT_ERROR is None:
        sentry_sdk.capture_exception(exc)


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
        for key in query_string:
            if key.lower() in SENSITIVE_KEYS:
                query_string[key] = "REDACTED"

        event["request"]["query_string"] = urllib.parse.urlencode(
            query_string, doseq=True
        )

    # # Handle Headers that might include a secret (e.g. any Authorization header)
    if "request" in event and event["request"].get("headers"):
        for header_name in event["request"]["headers"]:
            if header_name.lower() in SENSITIVE_HEADERS:
                event["request"]["headers"][header_name] = "REDACTED"

    # # Handle request body data
    if "request" in event and event["request"].get("data"):
        for key in event["request"]["data"]:
            if key.lower() in SENSITIVE_KEYS:
                event["request"]["data"][key] = "REDACTED"

    return event


def setup_sentry(config=None, *, dsn=None, **kwargs):
    """
    Initializes the Sentry SDK, with the Flask and Boto3 integrations added.

    Nothing is set up when sentry-sdk is not installed, when the ``ENV`` setting is
    ``development`` or ``testing``, or when no DSN is found. :py:func:`~flask_quickstart.create_app`
    calls this for you.

    :param config: The app config. Its ``ENV`` setting is used as the Sentry environment.
    :param dsn: The Sentry DSN. Defaults to the ``SENTRY_DSN`` setting, or the ``SENTRY_DSN`` or
        ``FLASK_SENTRY_DSN`` environment variables.
    :param kwargs: Options for ``sentry_sdk.init()``. ``traces_sample_rate`` defaults to
        ``0.1``. With ``debug=True``, events are printed instead of sent.
    """

    if SENTRY_IMPORT_ERROR is not None:
        logger.warning(
            "Sentry cannot be instantiated, it failed to import in this virtual environment: %s",
            SENTRY_IMPORT_ERROR,
        )
        return

    if config is None:
        config = {}

    if (config.get("ENV") or "").lower() in ("development", "testing"):
        print("[WARNING] Not setting up Sentry due to environment")
        return

    if dsn is None:
        dsn = config.get(
            "SENTRY_DSN",
            os.environ.get("SENTRY_DSN", os.environ.get("FLASK_SENTRY_DSN")),
        )

    # Using this as a truthy value, since we don't want to allow "", None or False as DSNs
    if not dsn:
        print("[WARNING] Cannot setup Sentry. No DSN found")
        return

    if not kwargs.get("transport"):
        # Let Sentry pick its default HTTP transport, except when debugging
        kwargs.pop("transport", None)
        if kwargs.get("debug") is True:
            kwargs["transport"] = PrintTransport

    if "environment" not in kwargs:
        kwargs["environment"] = config.get("ENV")

    if "integrations" not in kwargs or not kwargs["integrations"]:
        kwargs["integrations"] = []
    elif not isinstance(kwargs["integrations"], list):
        kwargs["integrations"] = [kwargs["integrations"]]

    add_boto3_int = True
    add_flask_int = True
    for integration in kwargs["integrations"]:
        if isinstance(integration, Boto3Integration):
            add_boto3_int = False
        elif isinstance(integration, FlaskIntegration):
            add_flask_int = False

    if add_boto3_int:
        kwargs["integrations"].append(Boto3Integration())
    if add_flask_int:
        kwargs["integrations"].append(FlaskIntegration())

    if "traces_sample_rate" not in kwargs:
        # 0 = no sampling, 1 = 100% sampling
        kwargs["traces_sample_rate"] = 0.1  # default is 10% of requests

    sentry_sdk.init(dsn=dsn, **kwargs)
