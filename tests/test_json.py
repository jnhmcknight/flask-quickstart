"""
tests.test_json
"""

import dataclasses
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import enum
import json
import uuid

from flask import jsonify
import pytest

from flask_quickstart.lib.json import ExtendedEncoder, extended_default


class Color(enum.Enum):
    RED = "red"


@dataclasses.dataclass
class Point:
    x: int
    y: int


@pytest.mark.parametrize(
    "value, expected",
    [
        (datetime(2026, 1, 1, 12, 30), "2026-01-01T12:30:00+00:00"),
        (
            datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc),
            "2026-01-01T12:30:00+00:00",
        ),
        (
            datetime(2026, 1, 1, 12, 30, tzinfo=timezone(timedelta(hours=-5))),
            "2026-01-01T17:30:00+00:00",
        ),
        (date(2026, 1, 2), "2026-01-02"),
        (timedelta(hours=1, minutes=2), "1:02:00"),
        (uuid.UUID(int=1), "00000000-0000-0000-0000-000000000001"),
        (Color.RED, "red"),
        ({1}, [1]),
        (Point(1, 2), {"x": 1, "y": 2}),
        (ValueError("boom"), "boom"),
    ],
)
def test_extended_default(value, expected):
    assert extended_default(value) == expected
    assert json.loads(json.dumps(value, cls=ExtendedEncoder)) == expected


@pytest.mark.parametrize("value", [object(), Point, Decimal("1.5")])
def test_extended_encoder_unsupported(value):
    with pytest.raises(TypeError):
        json.dumps(value, cls=ExtendedEncoder)


def test_app_json_provider(app):
    with app.app_context():
        resp = jsonify(
            when=datetime(2026, 1, 1, 12, 30),
            day=date(2026, 1, 2),
            color=Color.RED,
            point=Point(1, 2),
            ident=uuid.UUID(int=1),
            # Not handled by extended_default, so falls back to Flask's provider
            amount=Decimal("1.5"),
        )

    assert resp.json == {
        "when": "2026-01-01T12:30:00+00:00",
        "day": "2026-01-02",
        "color": "red",
        "point": {"x": 1, "y": 2},
        "ident": "00000000-0000-0000-0000-000000000001",
        "amount": "1.5",
    }


def test_app_json_provider_unsupported(app):
    with app.app_context(), pytest.raises(TypeError):
        jsonify(value=object())
