import dataclasses
import enum
import json
import uuid
from datetime import date, datetime, timedelta, timezone

from flask.json.provider import DefaultJSONProvider


def extended_default(obj):
    """Serialize the additional types that we care about, or raise TypeError."""

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, datetime):
        # Naive datetimes are assumed to already be in UTC
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.astimezone(timezone.utc).isoformat("T")
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return str(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, Exception):
        return str(obj)

    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class ExtendedEncoder(json.JSONEncoder):
    """Encoder that supports various additional types that we care about."""

    def default(self, obj):
        try:
            return extended_default(obj)
        except TypeError:
            return super().default(obj)


class ExtendedJSONProvider(DefaultJSONProvider):
    """Flask JSON provider (replaces the removed `app.json_encoder`) using ExtendedEncoder's types."""

    @staticmethod
    def default(o):
        try:
            return extended_default(o)
        except TypeError:
            return DefaultJSONProvider.default(o)
