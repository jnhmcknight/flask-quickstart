
from enum import Enum, EnumMeta

from werkzeug.routing import BaseConverter, ValidationError


def setup_enum_converter(enum_to_convert):

    if not isinstance(enum_to_convert, (Enum, EnumMeta,)):
        raise ValueError(f'{enum_to_convert.__name__} is not an Enum')

    class ConfiguredEnumConverter(BaseConverter):
        def to_python(self, value):
            try:
                return enum_to_convert[value]
            except (AttributeError, KeyError, IndexError, ValueError) as exc:
                raise ValidationError from exc

        def to_url(self, obj):
            if not isinstance(obj, enum_to_convert):
                raise ValidationError()

            return obj.name

    return ConfiguredEnumConverter
