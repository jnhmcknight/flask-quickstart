"""
tests.test_converters
"""

from datetime import date
import enum

from flask import url_for
import pytest

from flask_quickstart.converters import setup_enum_converter


class Color(enum.Enum):
    RED = 'red'
    GREEN = 'green'


@pytest.fixture()
def enum_app(app):
    app.url_map.converters['color'] = setup_enum_converter(Color)

    @app.route('/color/<color:color>')
    def color(color):
        assert isinstance(color, Color)
        return color.value

    @app.route('/day/<date:day>')
    def day(day):
        return day.isoformat()

    return app


def test_enum_converter_routing(enum_app):
    client = enum_app.test_client()

    assert client.get('/color/RED').text == 'red'
    assert client.get('/color/GREEN').text == 'green'
    assert client.get('/color/BLUE').status_code == 404
    assert client.get('/color/red').status_code == 404


def test_converters_build_urls(enum_app):
    with enum_app.test_request_context():
        assert url_for('color', color=Color.GREEN) == '/color/GREEN'
        assert url_for('day', day=date(2026, 3, 4)) == '/day/2026-03-04'


def test_enum_converter_rejects_other_values(enum_app):
    with enum_app.test_request_context(), pytest.raises(Exception):
        url_for('color', color='GREEN')


def test_setup_enum_converter_requires_enum():
    with pytest.raises(ValueError, match='not an Enum'):
        setup_enum_converter(str)
