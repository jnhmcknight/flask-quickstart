import random
import string

from flask import Response


def str2bool(s):
    """
    Converts a value to a :py:class:`bool`, treating ``"False"``, ``"false"``, ``"FALSE"`` and
    ``"0"`` as ``False``. Anything else uses its normal truthiness.
    """

    if s == "False" or s == "false" or s == "FALSE" or s == "0":
        return False
    return bool(s)


def random_string(length=5):
    """
    Returns a random string of ASCII letters and digits, generated with
    :py:class:`random.SystemRandom`.

    :param length: The length of the string
    """

    return "".join(
        random.SystemRandom().choice(
            string.ascii_lowercase + string.ascii_uppercase + string.digits
        )
        for _ in range(length)
    )


def forced_relative_redirect(url, **kwargs):
    """
    Returns a redirect response whose ``Location`` header is sent exactly as given, rather than
    being made into an absolute URL.

    :param url: The URL to redirect to
    :param kwargs: Keyword arguments for :py:class:`~flask.Response`. ``code`` may be used as an
        alias for ``status``. Pass a redirect status such as ``code=302``, since the default
        is ``200``.
    """

    body = f"""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<title>Redirecting...</title>
<h1>Redirecting...</h1>
<p>You should be redirected automatically to target URL: <a href="{url}">{url}</a>.  If not click the link.
    """

    if "code" in kwargs and "status" not in kwargs:
        kwargs.update({"status": kwargs.pop("code")})

    if "headers" not in kwargs:
        kwargs.update({"headers": {}})

    kwargs["headers"].update({"Location": url})
    resp = Response(
        body,
        **kwargs,
    )
    resp.autocorrect_location_header = False
    return resp
