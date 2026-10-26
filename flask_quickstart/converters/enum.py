from enum import Enum, EnumMeta

from werkzeug.routing import BaseConverter, ValidationError


def setup_enum_converter(enum_to_convert):
    """
    Creates a URL converter that matches the member names of an :py:class:`~enum.Enum`.

    The view receives the enum member, and :py:func:`~flask.url_for` accepts members of the enum
    only. Register the returned class in the app's ``url_map.converters`` to use it.

    :param enum_to_convert: The :py:class:`~enum.Enum` subclass to convert
    :returns: A Werkzeug ``BaseConverter`` subclass
    :raises ValueError: if ``enum_to_convert`` is not an :py:class:`~enum.Enum`
    """

    if not isinstance(
        enum_to_convert,
        (
            Enum,
            EnumMeta,
        ),
    ):
        raise ValueError(f"{enum_to_convert.__name__} is not an Enum")

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
