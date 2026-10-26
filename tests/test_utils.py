"""
tests.test_utils
"""

import string

import pytest

from flask_quickstart.utils import forced_relative_redirect, random_string, str2bool


@pytest.mark.parametrize(
    "value, expected",
    [
        ("False", False),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("", False),
        (None, False),
        ("true", True),
        ("1", True),
        ("anything", True),
    ],
)
def test_str2bool(value, expected):
    assert str2bool(value) is expected


def test_random_string():
    allowed = set(string.ascii_letters + string.digits)

    assert len(random_string()) == 5
    assert len(random_string(32)) == 32
    assert set(random_string(100)) <= allowed


@pytest.mark.parametrize(
    "kwargs, status_code",
    [
        ({}, 200),
        ({"code": 302}, 302),
        ({"status": 301}, 301),
    ],
)
def test_forced_relative_redirect(kwargs, status_code):
    resp = forced_relative_redirect("/target", **kwargs)

    assert resp.status_code == status_code
    assert resp.headers["Location"] == "/target"
    assert resp.autocorrect_location_header is False
    assert 'href="/target"' in resp.get_data(as_text=True)


def test_forced_relative_redirect_keeps_headers():
    resp = forced_relative_redirect("/target", code=302, headers={"X-Extra": "yes"})

    assert resp.headers["X-Extra"] == "yes"
    assert resp.headers["Location"] == "/target"


def test_forced_relative_redirect_is_not_made_absolute(app):
    @app.route("/redirect")
    def redirect():
        return forced_relative_redirect("/target", code=302)

    assert app.test_client().get("/redirect").headers["Location"] == "/target"
