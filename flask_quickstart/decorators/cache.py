
import inspect
import json
import logging
import os

from datetime import timedelta, datetime
from hashlib import sha1

from ..lib.json import ExtendedEncoder


logger = logging.getLogger(__name__)


class Cache:
    _data = None

    @classmethod
    def _serialize_args(cls, *args, **kwargs):  # pylint: disable=no-self-use
        call_args = {"args": args, "kwargs": kwargs}
        return json.dumps(call_args, cls=ExtendedEncoder, sort_keys=True, default=str)

    @classmethod
    def _make_key(cls, *args, **kwargs):
        return sha1(cls._serialize_args(*args, **kwargs).encode("utf-8")).hexdigest()

    @classmethod
    def _is_method(cls, func):
        spec = inspect.getargspec(func)
        return spec.args and spec.args[0] in ["self", "cls"]

    @classmethod
    def make_key(cls, wrapped_callable, *args, **kwargs):
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
    storage_folder = None
    prefix = None
    default_ttl = 900

    def __init__(self, storage_folder, *, prefix=None, default_ttl=None):
        if not storage_folder:
            raise ValueError('storage_folder must be a valid folder')

        self.storage_folder = storage_folder
        self.prefix = prefix

        if int(default_ttl) > 0:
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
    def _now(self):  # pylint: disable=no-self-use
        return datetime.utcnow()

    def _wrap(self, data, *, ttl=None, expire=False):
        expiry = self._now if expire else (self._now + timedelta(seconds=ttl or self.default_ttl))
        return {
            'expires': expiry,
            'data': data,
        }

    def _unwrap(self, data):
        return (data['data'], data['expires'], (self._now > data['expires']),)

    def expire(self, index=None):
        if index is not None:
            data, expires_at, is_expired = self.load(index)
            if data:
                return self.save(index, data, expire=True)
            else:
                return self.delete(index)

        for root, dirs, files in os.walk(self._storage_full_path):
            for file in files:
                try:
                    self.expire(file)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.excetion(exc)

    def clear(self):
        try:
            shutil.rmtree(self._storage_full_path)
            return True

        except OSError as exc:
            logger.exception(exc)
            return False

    def delete(self, index):
        try:
            return os.remove(self._get_full_path(index))

        except OSError:
            logger.exception(exc)
            return False

    def load(self, index, *, encoding=None):
        encoding = encoding if encoding is not None else 'utf-8'
        try:
            with open(self._get_full_path(index), 'r', encoding=encoding) as datafile:
                return self._unwrap(json.load(datafile))

        except OSError as exc:
            logger.exception(exc)
            return (None, datetime(1970, 1, 1, 0, 0), True)

    def save(self, index, data, *, encoding=None, ttl=None, expire=False):
        encoding = encoding if encoding is not None else 'utf-8'
        try:
            os.makedirs(self._storage_full_path, exist_ok=True)
            with open(self._get_full_path(index), 'w', encoding=encoding) as datafile:
                json.dump(self._wrap(data, ttl=ttl, expire=expire), datafile)
            return True

        except OSError as exc:
            logger.exception(exc)
            return False
