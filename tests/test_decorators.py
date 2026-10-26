"""
tests.test_decorators
"""

from datetime import datetime, timezone

import pytest

from flask_quickstart.decorators import memoize, ttl_memoize
from flask_quickstart.decorators.cache import Cache, TTLFileCache


@pytest.fixture()
def cache_app(make_app, tmp_path):
    app = make_app(CACHE_STORAGE_FOLDER=str(tmp_path))
    with app.app_context():
        yield app


@pytest.fixture()
def ttl_cache(tmp_path):
    return TTLFileCache(str(tmp_path), prefix='prefixed', default_ttl=60)


def test_cache_key_is_stable():
    def func(a, b=None):
        pass

    assert Cache.make_key(func, 1, b=2) == Cache.make_key(func, 1, b=2)
    assert Cache.make_key(func, 1, b=2) != Cache.make_key(func, 1, b=3)


def test_cache_key_ignores_self():
    class Thing:
        def method(self, a):
            pass

    assert Cache.make_key(Thing.method, Thing(), 1) == Cache.make_key(Thing.method, Thing(), 1)


def test_in_memory_cache():
    cache = Cache()

    assert cache.load('key') is None
    assert cache.save('key', {'a': 1})
    assert cache.load('key') == {'a': 1}

    cache.delete('key')
    assert cache.load('key') is None

    cache.save('key', 1)
    cache.clear()
    assert cache.load('key') is None


def test_ttl_file_cache_requires_folder():
    with pytest.raises(ValueError):
        TTLFileCache('')


def test_ttl_file_cache_default_ttl(tmp_path):
    assert TTLFileCache(str(tmp_path)).default_ttl == 900
    assert TTLFileCache(str(tmp_path), default_ttl='30').default_ttl == 30


def test_ttl_file_cache_roundtrip(ttl_cache, tmp_path):
    assert ttl_cache.save('key', {'when': datetime(2026, 1, 1)})
    assert (tmp_path / 'prefixed' / 'key').is_file()

    data, expires_at, is_expired = ttl_cache.load('key')
    assert data == {'when': '2026-01-01T00:00:00+00:00'}
    assert expires_at > datetime.now(timezone.utc)
    assert not is_expired


def test_ttl_file_cache_missing_entry(ttl_cache):
    data, expires_at, is_expired = ttl_cache.load('missing')

    assert data is None
    assert expires_at < datetime.now(timezone.utc)
    assert is_expired


def test_ttl_file_cache_corrupt_entry(ttl_cache, tmp_path):
    (tmp_path / 'prefixed').mkdir()
    (tmp_path / 'prefixed' / 'key').write_text('not json')

    assert ttl_cache.load('key')[0] is None


def test_ttl_file_cache_expire(ttl_cache):
    ttl_cache.save('one', 1)
    ttl_cache.save('two', 2)

    ttl_cache.expire('one')
    assert ttl_cache.load('one') [::2] == (1, True)
    assert ttl_cache.load('two') [::2] == (2, False)

    ttl_cache.expire()
    assert ttl_cache.load('two') [::2] == (2, True)


def test_ttl_file_cache_delete_and_clear(ttl_cache, tmp_path):
    ttl_cache.save('key', 1)

    assert ttl_cache.delete('key')
    assert ttl_cache.load('key')[0] is None
    assert ttl_cache.delete('key')

    ttl_cache.save('key', 1)
    assert ttl_cache.clear()
    assert not (tmp_path / 'prefixed').exists()


def test_memoize(app):
    calls = []

    @memoize()
    def double(value):
        calls.append(value)
        return value * 2

    with app.app_context():
        assert double(2) == 4
        assert double(2) == 4
        assert double(3) == 6

    assert calls == [2, 3]


@pytest.mark.parametrize('force_refresh', [True, lambda: True])
def test_memoize_force_refresh(app, force_refresh):
    calls = []

    @memoize(force_refresh)
    def double(value):
        calls.append(value)
        return value * 2

    with app.app_context():
        double(2)
        double(2)

    assert calls == [2, 2]


def test_memoize_method(app):
    calls = []

    class Thing:
        @memoize()
        def double(self, value):
            calls.append(value)
            return value * 2

    with app.app_context():
        assert Thing().double(2) == 4
        assert Thing().double(2) == 4

    assert calls == [2]


def test_ttl_memoize(cache_app):
    calls = []

    @ttl_memoize()
    def lookup(value):
        calls.append(value)
        return {'value': value}

    assert lookup(1) == {'value': 1}
    assert lookup(1) == {'value': 1}
    assert lookup(2) == {'value': 2}
    assert calls == [1, 2]


@pytest.mark.parametrize('force_refresh', [True, lambda: True])
def test_ttl_memoize_force_refresh(cache_app, force_refresh):
    calls = []

    @ttl_memoize(force_refresh)
    def lookup(value):
        calls.append(value)
        return {'value': value, 'call': len(calls)}

    assert lookup(1) == {'value': 1, 'call': 1}
    assert lookup(1) == {'value': 1, 'call': 2}


def test_ttl_memoize_refreshes_expired_entries(cache_app):
    calls = []

    @ttl_memoize()
    def lookup(value):
        calls.append(value)
        return {'call': len(calls)}

    assert lookup(1) == {'call': 1}
    lookup.__wrapped__.cache.expire()
    assert lookup(1) == {'call': 2}


def test_ttl_memoize_serves_stale_data_on_failure(cache_app):
    should_fail = False

    @ttl_memoize(lambda: should_fail)
    def lookup():
        if should_fail:
            raise RuntimeError('upstream is down')
        return {'fresh': True}

    assert lookup() == {'fresh': True}

    should_fail = True
    assert lookup() == {'fresh': True}


def test_ttl_memoize_raises_without_cached_data(cache_app):
    @ttl_memoize()
    def lookup():
        raise RuntimeError('upstream is down')

    with pytest.raises(RuntimeError):
        lookup()


def test_ttl_memoize_removes_empty_results(cache_app):
    results = [{'value': 1}, None]

    @ttl_memoize(lambda: True)
    def lookup():
        return results.pop(0)

    assert lookup() == {'value': 1}
    assert lookup() is None
    assert lookup.__wrapped__.cache.load(lookup.__wrapped__.cache.make_key(lookup.__wrapped__))[0] is None


def test_ttl_memoize_without_storage_folder(app):
    calls = []

    @ttl_memoize()
    def lookup():
        calls.append(1)
        return {'value': 1}

    with app.app_context():
        lookup()
        lookup()

    assert len(calls) == 2
