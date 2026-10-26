import inspect
import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from hashlib import sha1

from ..lib.json import ExtendedEncoder

logger = logging.getLogger(__name__)


class Cache:
    """An in-memory cache, used by :py:func:`~flask_quickstart.decorators.memoize`."""

    _data = None

    @classmethod
    def _serialize_args(cls, *args, **kwargs):
        call_args = {"args": args, "kwargs": kwargs}
        return json.dumps(call_args, cls=ExtendedEncoder, sort_keys=True, default=str)

    @classmethod
    def _make_key(cls, *args, **kwargs):
        return sha1(cls._serialize_args(*args, **kwargs).encode("utf-8")).hexdigest()

    @classmethod
    def _is_method(cls, func):
        params = list(inspect.signature(func).parameters)
        return bool(params) and params[0] in ["self", "cls"]

    @classmethod
    def make_key(cls, wrapped_callable, *args, **kwargs):
        """
        Returns the cache key for a call to ``wrapped_callable`` with the given arguments. When
        it is a method, the ``self`` or ``cls`` argument is left out of the key.
        """

        # Have to mangle the args when we're decorating a class method so that the `self`
        # arg doesn't mess with the cache key
        argscopy = args[1:] if cls._is_method(wrapped_callable) else args
        return cls._make_key(*argscopy, **kwargs)

    def __init__(self):
        self._data = {}

    def clear(self):
        self._data = {}

    def delete(self, index):
        self._data.pop(index, None)

    def load(self, index):
        return self._data.get(index)

    def save(self, index, data):
        self._data.update({index: data})
        return True


class TTLFileCache(Cache):
    """
    A cache that stores each entry as a JSON file with an expiry time, used by
    :py:func:`~flask_quickstart.decorators.ttl_memoize`.

    Expired entries are not removed; :py:meth:`load` reports them as expired so the caller can
    decide whether to refresh them or keep using them.

    :param storage_folder: The folder to store entries in
    :param prefix: A subfolder of ``storage_folder`` to use
    :param default_ttl: How many seconds entries are valid for. Defaults to 900.
    """

    storage_folder = None
    prefix = None
    default_ttl = 900

    def __init__(self, storage_folder, *, prefix=None, default_ttl=None):
        if not storage_folder:
            raise ValueError("storage_folder must be a valid folder")

        self.storage_folder = storage_folder
        self.prefix = prefix

        if default_ttl and int(default_ttl) > 0:
            self.default_ttl = int(default_ttl)

    @property
    def _storage_full_path(self):

        if self.prefix:
            return os.path.join(
                self.storage_folder,
                self.prefix,
            )

        return self.storage_folder

    def _get_full_path(self, index):
        return os.path.join(
            self._storage_full_path,
            index,
        )

    @property
    def _now(self):
        return datetime.now(timezone.utc)

    def _wrap(self, data, *, ttl=None, expire=False):
        expiry = (
            self._now
            if expire
            else (self._now + timedelta(seconds=ttl or self.default_ttl))
        )
        return {
            "expires": expiry.isoformat(),
            "data": data,
        }

    def _unwrap(self, data):
        expires = datetime.fromisoformat(data["expires"])
        return (
            data["data"],
            expires,
            (self._now > expires),
        )

    def expire(self, index=None):
        """
        Marks an entry as expired, or every entry when ``index`` is not given. Entries without
        data are deleted instead.
        """

        if index is not None:
            data = self.load(index)[0]
            if data:
                return self.save(index, data, expire=True)
            else:
                return self.delete(index)

        for _, _, files in os.walk(self._storage_full_path):
            for file in files:
                try:
                    self.expire(file)
                except Exception:  # pylint: disable=broad-except
                    logger.exception("Failed to expire cache entry %s", file)

    def clear(self):
        """Deletes every entry, by removing the cache's folder. Returns whether it succeeded."""

        try:
            shutil.rmtree(self._storage_full_path)
            return True

        except OSError:
            logger.exception("Failed to clear cache folder %s", self._storage_full_path)
            return False

    def delete(self, index):
        """Deletes an entry. Returns whether it is now absent."""

        try:
            os.remove(self._get_full_path(index))
            return True

        except FileNotFoundError:
            return True

        except OSError:
            logger.exception("Failed to delete cache entry %s", index)
            return False

    def load(self, index, *, encoding=None):
        """
        Loads an entry.

        :returns: A ``(data, expires_at, is_expired)`` tuple. ``data`` is ``None`` when there is
            no readable entry, in which case it is reported as expired.
        """

        encoding = encoding if encoding is not None else "utf-8"
        try:
            with open(self._get_full_path(index), encoding=encoding) as datafile:
                return self._unwrap(json.load(datafile))

        except FileNotFoundError:
            pass

        except (OSError, ValueError, KeyError):
            logger.exception("Failed to load cache entry %s", index)

        return (None, datetime(1970, 1, 1, tzinfo=timezone.utc), True)

    def save(self, index, data, *, encoding=None, ttl=None, expire=False):
        """
        Saves an entry. Returns whether it succeeded.

        :param ttl: How many seconds the entry is valid for, instead of the default
        :param expire: Save the entry as already expired
        """

        encoding = encoding if encoding is not None else "utf-8"
        try:
            os.makedirs(self._storage_full_path, exist_ok=True)
            with open(self._get_full_path(index), "w", encoding=encoding) as datafile:
                json.dump(
                    self._wrap(data, ttl=ttl, expire=expire),
                    datafile,
                    cls=ExtendedEncoder,
                )
            return True

        except (OSError, TypeError):
            logger.exception("Failed to save cache entry %s", index)
            return False
