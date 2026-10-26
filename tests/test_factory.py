"""
tests.test_factory
"""

import logging
import re
from datetime import date

import pytest
from flask import Response

from flask_quickstart import factory
from flask_quickstart.lib.json import ExtendedJSONProvider


def add_routes(app):
    @app.route("/text")
    def text():
        return "hello"

    @app.route("/image")
    def image():
        return Response(b"not really a png", mimetype="image/png")

    @app.route("/missing-image")
    def missing_image():
        return Response(b"", status=404, mimetype="image/png")

    @app.route("/remote-addr")
    def remote_addr():
        from flask import request

        return request.remote_addr

    @app.route("/day/<date:day>")
    def day(day):
        assert isinstance(day, date)
        return day.isoformat()

    return app


@pytest.mark.parametrize(
    "value, expected",
    [
        ("example.com", False),
        ("https://example.com", False),
        (".*", True),
        (r".*\.example\.com", True),
        ("[a-z]+.example.com", True),
        (re.compile("example"), True),
    ],
)
def test_probably_regex(value, expected):
    assert factory.probably_regex(value) == expected


@pytest.mark.parametrize(
    "origins, expected",
    [
        ("example.com", ["https://example.com"]),
        (
            ["example.com", "http://example.org"],
            ["https://example.com", "http://example.org"],
        ),
        (
            '["example.com", "https://example.org"]',
            ["https://example.com", "https://example.org"],
        ),
        (("example.com",), ["https://example.com"]),
    ],
)
def test_origins_list_to_regex_literals(origins, expected):
    assert factory.origins_list_to_regex(origins) == expected


def test_origins_list_to_regex_compiles_regexes():
    (pattern,) = factory.origins_list_to_regex([r".*\.example\.com"])

    assert isinstance(pattern, re.Pattern)
    assert pattern.pattern == r"(?:https://.*\.example\.com)\Z"
    assert pattern.flags & re.IGNORECASE


@pytest.mark.parametrize(
    "origin, expected",
    [
        ("https://example.com", True),
        ("https://EXAMPLE.com", True),
        ("https://sub.example.org", True),
        ("https://SUB.EXAMPLE.ORG", True),
        ("https://sub.example.net", True),
        ("http://example.com", False),
        ("https://evil.com", False),
        ("https://example.com.evil.com", False),
        ("https://sub.example.org.evil.com", False),
        ("https://sub.example.org\n", False),
        ("https://sub.example.net.evil.com", False),
    ],
)
def test_matches_any_origin(origin, expected):
    patterns = factory.origins_list_to_regex(
        ["example.com", r".*\.example\.org", r".*\.example\.net$"]
    )
    assert factory.matches_any_origin(origin, patterns) == expected


def test_create_app_defaults(app):
    assert app.name == "testing"
    assert isinstance(app.json, ExtendedJSONProvider)
    assert app.config.ENV == "testing"
    assert "date" in app.url_map.converters
    assert app.logger.level == logging.WARNING


def test_create_app_kwargs(make_app, monkeypatch):
    monkeypatch.setenv("FLASK_FROM_ENV", "env-value")
    app = factory.create_app(
        "kwargs",
        log_level=logging.DEBUG,
        flask_kwargs={"static_folder": None},
        dynaconf_kwargs={"LOADERS_FOR_DYNACONF": []},
    )

    assert app.logger.level == logging.DEBUG
    assert app.static_folder is None
    # Env vars are always loaded, even when other loaders are specified
    assert app.config.FROM_ENV == "env-value"


def test_create_app_retries(monkeypatch):
    attempts = []
    real_create_app = factory._create_app

    def flaky_create_app(*args, **kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("transient failure")
        return real_create_app(*args, **kwargs)

    monkeypatch.setattr(factory, "_create_app", flaky_create_app)
    monkeypatch.setattr(factory.time, "sleep", lambda _: None)

    assert factory.create_app("retried").name == "retried"
    assert len(attempts) == 3


def test_create_app_gives_up(monkeypatch):
    attempts = []

    def broken_create_app(*args, **kwargs):
        attempts.append(1)
        raise RuntimeError("permanent failure")

    monkeypatch.setattr(factory, "_create_app", broken_create_app)
    monkeypatch.setattr(factory.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="permanent failure"):
        factory.create_app("broken")
    assert len(attempts) == 5


def test_date_converter_routing(app):
    client = add_routes(app).test_client()

    assert client.get("/day/2026-03-04").text == "2026-03-04"
    assert client.get("/day/2026-13-04").status_code == 404
    assert client.get("/day/not-a-date").status_code == 404


@pytest.mark.parametrize(
    "origin, allowed",
    [
        ("https://example.com", True),
        ("https://www.example.org", True),
        ("https://evil.com", False),
        ("https://www.example.org.evil.com", False),
        ("http://example.com", False),
    ],
)
def test_cors(make_app, origin, allowed):
    app = add_routes(make_app(ALLOWED_ORIGINS=["example.com", r".*\.example\.org"]))
    resp = app.test_client().get("/text", headers={"Origin": origin})

    assert (resp.headers.get("Access-Control-Allow-Origin") == origin) == allowed
    if allowed:
        assert resp.headers["Access-Control-Allow-Credentials"] == "true"


def test_cors_allows_no_origins_by_default(app):
    resp = (
        add_routes(app)
        .test_client()
        .get("/text", headers={"Origin": "https://example.com"})
    )

    assert "Access-Control-Allow-Origin" not in resp.headers


def test_cors_allow_any_https_origin(make_app):
    app = add_routes(make_app(ALLOWED_ORIGINS=[".*"]))
    client = app.test_client()

    origin = "https://anything.example"
    assert (
        client.get("/text", headers={"Origin": origin}).headers[
            "Access-Control-Allow-Origin"
        ]
        == origin
    )
    assert (
        "Access-Control-Allow-Origin"
        not in client.get(
            "/text", headers={"Origin": "http://anything.example"}
        ).headers
    )


@pytest.mark.parametrize(
    "headers, status_code",
    [
        ({"Origin": "https://example.com"}, 200),
        ({"Origin": "https://EXAMPLE.COM"}, 200),
        ({"Origin": "https://evil.com"}, 403),
        ({}, 403),
    ],
)
def test_shortcircuit_options(make_app, headers, status_code):
    app = add_routes(
        make_app(ALLOWED_ORIGINS=["example.com"], SHORTCIRCUIT_OPTIONS=True)
    )
    resp = app.test_client().options("/text", headers=headers)

    assert resp.status_code == status_code
    if status_code == 200:
        assert resp.text == ""


def test_shortcircuit_options_without_allowed_origins(make_app):
    app = add_routes(make_app(SHORTCIRCUIT_OPTIONS=True))
    resp = app.test_client().options("/text", headers={"Origin": "https://example.com"})

    assert resp.status_code == 403


def test_options_not_shortcircuited_by_default(make_app):
    app = add_routes(make_app(ALLOWED_ORIGINS=["example.com"]))
    resp = app.test_client().options("/text", headers={"Origin": "https://evil.com"})

    # Flask's automatic OPTIONS handling responds instead
    assert resp.status_code == 200
    assert "GET" in resp.headers["Allow"]


def test_relative_redirects(make_app):
    app = add_routes(make_app(RELATIVE_REDIRECTS=True))
    client = app.test_client()

    resp = client.get("/text/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/text"

    assert client.get("/text").status_code == 200
    assert client.get("/").status_code == 404


@pytest.mark.parametrize(
    "query_string",
    ["q=1", "q=a%20b&x=%2F", "q=caf%C3%A9"],
)
def test_relative_redirects_keep_query_string(make_app, query_string):
    app = add_routes(make_app(RELATIVE_REDIRECTS=True))
    resp = app.test_client().get(f"/text/?{query_string}")

    assert resp.status_code == 302
    assert resp.headers["Location"] == f"/text?{query_string}"


@pytest.mark.parametrize("path", ["//evil.com/", "///evil.com/", "/\\evil.com/"])
def test_relative_redirects_stay_on_site(make_app, path):
    app = make_app(RELATIVE_REDIRECTS=True)
    resp = app.test_client().get("/", environ_overrides={"PATH_INFO": path})

    location = resp.headers["Location"]
    assert location.startswith("/")
    assert not location.startswith(("//", "/\\"))


def test_trailing_slash_without_relative_redirects(app):
    assert add_routes(app).test_client().get("/text/").status_code == 404


@pytest.mark.parametrize(
    "path, cached",
    [
        ("/image", True),
        ("/text", False),
        ("/missing-image", False),
    ],
)
def test_cache_headers(make_app, path, cached):
    app = add_routes(make_app(ADD_CACHE_HEADERS=True))
    resp = app.test_client().get(path)

    assert ("immutable" in resp.headers.get("Cache-Control", "")) == cached
    assert ("Accept-Encoding" in resp.headers.get("Vary", "")) == cached


def test_cache_headers_respect_existing(make_app):
    app = make_app(ADD_CACHE_HEADERS=True)

    @app.route("/custom")
    def custom():
        return Response(
            b"x", mimetype="image/png", headers={"Cache-Control": "no-store"}
        )

    assert app.test_client().get("/custom").headers["Cache-Control"] == "no-store"


def test_cache_headers_without_content_type(make_app):
    app = make_app(ADD_CACHE_HEADERS=True)

    @app.route("/no-content-type")
    def no_content_type():
        resp = Response(b"x")
        del resp.headers["Content-Type"]
        return resp

    assert (
        "immutable"
        in app.test_client().get("/no-content-type").headers["Cache-Control"]
    )


def test_no_cache_headers_by_default(app):
    resp = add_routes(app).test_client().get("/image")
    assert "Cache-Control" not in resp.headers


def test_proxy_fix(make_app):
    app = add_routes(make_app(NUM_PROXIES=1))
    resp = app.test_client().get(
        "/remote-addr",
        headers={"X-Forwarded-For": "203.0.113.1"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )

    assert resp.text == "203.0.113.1"


def test_no_proxy_fix_by_default(app):
    resp = (
        add_routes(app)
        .test_client()
        .get(
            "/remote-addr",
            headers={"X-Forwarded-For": "203.0.113.1"},
            environ_base={"REMOTE_ADDR": "10.0.0.1"},
        )
    )

    assert resp.text == "10.0.0.1"


def test_default_csp(app):
    resp = add_routes(app).test_client().get("/text")
    assert resp.headers["Content-Security-Policy"] == "default-src 'self'"


def test_configured_csp(make_app):
    app = add_routes(
        make_app(
            CSP_DEFAULT_SRC=["https:", "self"],
            CSP_UPGRADE_INSECURE_REQUESTS=True,
        )
    )
    resp = app.test_client().get("/text")

    assert resp.headers["Content-Security-Policy"] == (
        "default-src https: 'self'; upgrade-insecure-requests"
    )


def test_report_only_csp(make_app):
    app = add_routes(
        make_app(
            CSP_REPORT_ONLY=True,
            CSP_REPORT_URI="https://example.com/csp",
        )
    )
    resp = app.test_client().get("/text")

    assert "Content-Security-Policy" not in resp.headers
    assert resp.headers["Content-Security-Policy-Report-Only"] == (
        "default-src 'self'; report-uri https://example.com/csp"
    )
