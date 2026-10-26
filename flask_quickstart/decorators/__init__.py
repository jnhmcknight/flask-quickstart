from functools import wraps

from flask import current_app

from ..utils.sentry import capture_exception
from .cache import Cache, TTLFileCache


def memoize(force_refresh_callable=None):
    """
    Decorator that caches a function's return values in memory, keyed on its arguments.

    The cache lives for the life of the process. Falsy return values are not served from the
    cache, so the function is called again for them. Must be called within an app context.

    Taken and modified from Python Decorator Library.
    https://wiki.python.org/moin/PythonDecoratorLibrary#Alternate_memoize_as_dict_subclass

    :param force_refresh_callable: A value, or a callable returning one, that when truthy causes
        the function to be called and the cache to be refreshed
    """

    def decorator(obj):
        @wraps(obj)
        def memoizer(*args, **kwargs):
            if getattr(obj, "cache", None) is None:
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

            index = obj.cache.make_key(obj, *args, **kwargs)
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
    Decorator that caches a function's return values on the file system for a limited time,
    using :py:class:`~flask_quickstart.decorators.cache.TTLFileCache`.

    Entries are stored under the ``CACHE_STORAGE_FOLDER`` setting, in a folder named after the
    function. Without that setting, nothing is cached. Return values must be JSON-serializable by
    :py:class:`~flask_quickstart.lib.json.ExtendedEncoder`, and are returned from the cache as
    their JSON-decoded form.

    If refreshing an entry raises an exception, it is reported to Sentry and the previously
    cached value is returned when there is one. An empty return value removes the cached entry.
    Must be called within an app context.

    :param force_refresh_callable: A value, or a callable returning one, that when truthy causes
        the function to be called and the cache to be refreshed
    :param default_ttl: How many seconds entries are cached for. Defaults to the ``CACHE_TTL``
        setting, or 900.
    """

    def decorator(obj):
        @wraps(obj)
        def wrapper(*args, **kwargs):
            if not current_app.config.get("CACHE_STORAGE_FOLDER"):
                current_app.logger.debug(
                    "Calling underlying memoized function, due to missing CACHE_STORAGE_FOLDER config"
                )
                return obj(*args, **kwargs)

            if getattr(obj, "cache", None) is None:
                obj.cache = TTLFileCache(
                    current_app.config.CACHE_STORAGE_FOLDER,
                    prefix=obj.__name__,
                    default_ttl=default_ttl or current_app.config.get("CACHE_TTL"),
                )

            index = obj.cache.make_key(obj, *args, **kwargs)
            current_app.logger.debug("Cache key is: %s", index)

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
                    current_app.logger.exception(
                        "Memoized function %s failed", obj.__name__
                    )
                    if data:
                        current_app.logger.warning(
                            "Serving response from the cache, memoized function failed"
                        )
                        return data

                    raise

                if newdata:
                    if obj.cache.save(index, newdata):
                        current_app.logger.debug("Saved to cache")

                else:
                    current_app.logger.debug(
                        "Upstream response was empty, ensuring old cached entry is removed"
                    )
                    obj.cache.delete(index)

                data = newdata

            else:
                current_app.logger.debug(
                    "Serving response from the cache, expires at: %s", expires_at
                )

            return data

        return wrapper

    return decorator
