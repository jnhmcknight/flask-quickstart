# -*- coding: utf-8 -*-

import inspect
import json
import logging

from functools import wraps
from hashlib import sha1

from ..lib.json import ExtendedEncoder


logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)


def _serialize_args(*args, **kwargs):
    call_args = {"args": args, "kwargs": kwargs}
    return json.dumps(call_args, cls=ExtendedEncoder, sort_keys=True, default=str)


def _make_key(*args, **kwargs):
    return sha1(_serialize_args(*args, **kwargs).encode("utf-8")).hexdigest()


def _is_method(func):
    spec = inspect.getargspec(func)
    return spec.args and spec.args[0] in ["self", "cls"]


def memoize(force_refresh_callable=None):
    """
    Simple decorator to cache return value based on args and kwargs in-memory.

    Taken and modified from Python Decorator Library.
    https://wiki.python.org/moin/PythonDecoratorLibrary#Alternate_memoize_as_dict_subclass

    """

    def decorator(obj):
        cache = obj.__memo_cache__ = {}

        @wraps(obj)
        def memoizer(*args, **kwargs):
            force_refresh = False
            if force_refresh_callable is not None:
                if callable(force_refresh_callable):
                    logger.debug(
                        "Using return value of force_refresh_callable to determine refresh forcing"
                    )
                    force_refresh = force_refresh_callable()
                else:
                    logger.debug(
                        "Using value of force_refresh_callable to determine refresh forcing"
                    )
                    force_refresh = force_refresh_callable

            # Have to mangle the args when we're decorating a class method so that the `self`
            # arg doesn't mess with the cache key
            argscopy = args[1:] if _is_method(obj) else args
            key = _make_key(*argscopy, **kwargs)

            if key not in cache or force_refresh:
                logger.debug("Calling underlying memoized function")
                cache[key] = obj(*args, **kwargs)
            else:
                logger.debug("Serving response from the cache")

            return cache[key]

        return memoizer

    return decorator
