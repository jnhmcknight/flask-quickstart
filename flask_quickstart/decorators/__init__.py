
from functools import wraps

from flask import current_app

from .cache import Cache, TTLFileCache


def memoize(force_refresh_callable=None):
    """
    Simple decorator to cache return value based on args and kwargs in-memory.

    Taken and modified from Python Decorator Library.
    https://wiki.python.org/moin/PythonDecoratorLibrary#Alternate_memoize_as_dict_subclass

    """

    def decorator(obj):
        @wraps(obj)
        def memoizer(*args, **kwargs):
            if not obj.cache:
                obj.cache = Cache()

            force_refresh = False
            if force_refresh_callable is not None:
                if callable(force_refresh_callable):
                    current_app.logger.debug(
                        "Using return value of force_refresh_callable to determine refresh forcing"
                    )
                    force_refresh = force_refresh_callable()
                else:
                    current_app.logger.debug(
                        "Using value of force_refresh_callable to determine refresh forcing"
                    )
                    force_refresh = force_refresh_callable

            index = obj.cache.make_key(obj, *argscopy, **kwargs)
            data = obj.cache.load(index)

            if not data or force_refresh:
                current_app.logger.debug("Calling underlying memoized function")
                data = obj(*args, **kwargs)
                obj.cache.save(index, data)

            else:
                current_app.logger.debug("Serving response from the cache")

            return data

        return memoizer

    return decorator


def ttl_memoize(force_refresh_callable=None, *, default_ttl=None):
    """
    Decorator to cache return values on the file system
    """

    def decorator(obj):
        @wraps(obj)
        def wrapper(*args, **kwargs):
            if not current_app.config.get("CACHE_STORAGE_FOLDER"):
                current_app.logger.debug(
                    "Calling underlying memoized function, due to missing CACHE_STORAGE_FOLDER config"
                )
                return obj(*args, **kwargs)

            if not obj.cache:
                obj.cache = TTLFileCache(
                    current_app.config.CACHE_STORAGE_FOLDER,
                    prefix=obj.__name__,
                    default_ttl=default_ttl or current_app.config.get("CACHE_TTL"),
                )

            index = obj.cache.make_key(obj, *argscopy, **kwargs)
            current_app.logger.debug("Cache key is: %s" % index)

            data, expires_at, force_refresh = obj.cache.load(index)

            if force_refresh_callable is not None:
                if callable(force_refresh_callable):
                    current_app.logger.debug(
                        "Using return value of force_refresh_callable to determine refresh forcing"
                    )
                    force_refresh = force_refresh_callable()
                else:
                    current_app.logger.debug(
                        "Using value of force_refresh_callable to determine refresh forcing"
                    )
                    force_refresh = force_refresh_callable

            if not data:
                current_app.logger.debug("Refresh forced, cache entry is empty")
                force_refresh = True

            if force_refresh:
                current_app.logger.debug("Calling underlying memoized function")
                newdata = None
                try:
                    newdata = obj(*args, **kwargs)

                except Exception as exc:
                    capture_exception(exc)
                    current_app.logger.exception(exc)
                    if data:
                        current_app.logger.warn(
                            "Serving response from the cache, memoized function failed"
                        )
                        return data

                    raise exc

                if newdata:
                    if obj.cache.save(index, newdata):
                        current_app.logger.debug(
                            "Saved to cache, will expire at: %s" % expires_at
                        )

                else:
                    current_app.logger.debug(
                        "Upstream response was empty, ensuring old cached entry is removed"
                    )
                    obj.cache.delete(index)

            else:
                current_app.logger.debug(
                    "Serving response from the cache, expires at: %s" % expires_at
                )

            return data

        return wrapper

    return decorator
