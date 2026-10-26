API Docs
========

App factory
~~~~~~~~~~~

Most of this package is set up for you by :py:func:`~flask_quickstart.create_app`, and controlled
by the :doc:`configuration <configuration>`.

.. autofunction:: flask_quickstart.create_app

JSON
~~~~

Apps created by ``create_app`` use :py:class:`~flask_quickstart.lib.json.ExtendedJSONProvider`,
so :py:func:`~flask.json.jsonify` and views returning a :py:class:`dict` or :py:class:`list` can
include these types:

================================  =========================================================
Type                              Serialized as
================================  =========================================================
:py:class:`~datetime.datetime`    ISO 8601 in UTC, e.g. ``2026-01-01T12:30:00+00:00``.
                                  Naive datetimes are assumed to be in UTC.
:py:class:`~datetime.date`        ISO 8601, e.g. ``2026-01-02``
:py:class:`~datetime.timedelta`   ``str()``, e.g. ``1:02:00``
:py:class:`~uuid.UUID`            ``str()``
:py:class:`~enum.Enum`            The member's value
:py:class:`set`                   A list
dataclass instances               An object, via :py:func:`dataclasses.asdict`
:py:class:`Exception`             ``str()``
================================  =========================================================

Anything else is handled by Flask's default provider, which also supports
:py:class:`~decimal.Decimal`.

.. code:: python

    @app.route('/event')
    def event():
        return {'id': uuid.uuid4(), 'starts': datetime.now(timezone.utc)}

.. autoclass:: flask_quickstart.lib.json.ExtendedJSONProvider(app)

.. autoclass:: flask_quickstart.lib.json.ExtendedEncoder

To encode these types outside of a request, pass it to :py:func:`json.dumps`:

.. code:: python

    json.dumps(data, cls=ExtendedEncoder)

.. autofunction:: flask_quickstart.lib.json.extended_default

URL converters
~~~~~~~~~~~~~~

The ``date`` converter is registered on apps created by ``create_app``. It matches ``YYYY-MM-DD``
and passes the view a :py:class:`~datetime.date`. Invalid dates, such as ``2026-13-01``, give a
``404``.

.. code:: python

    @app.route('/archive/<date:day>')
    def archive(day):
        ...

    url_for('archive', day=date(2026, 3, 4))  # '/archive/2026-03-04'

.. autoclass:: flask_quickstart.converters.DateConverter(map)

Enum converters need to be created for each enum and registered:

.. code:: python

    from flask_quickstart.converters import setup_enum_converter

    class Color(enum.Enum):
        RED = 'red'
        GREEN = 'green'

    app.url_map.converters['color'] = setup_enum_converter(Color)

    @app.route('/paint/<color:color>')
    def paint(color):
        return color.value  # '/paint/RED' -> 'red'

.. autofunction:: flask_quickstart.converters.setup_enum_converter

Caching
~~~~~~~

Two decorators cache a function's return values, keyed on its arguments. Both can be used on
methods, in which case ``self`` is left out of the key, and both need an app context.

:py:func:`~flask_quickstart.decorators.memoize` keeps values in memory for the life of the
process. :py:func:`~flask_quickstart.decorators.ttl_memoize` stores them on disk for a limited
time, and keeps serving the cached value if refreshing it fails:

.. code:: python

    from flask_quickstart.decorators import ttl_memoize

    @ttl_memoize(default_ttl=300)
    def exchange_rates(currency):
        return requests.get(f'https://api.example.com/rates/{currency}').json()

Each decorator takes a ``force_refresh_callable``, to bypass the cache when it returns a truthy
value:

.. code:: python

    @ttl_memoize(lambda: request.args.get('refresh') == '1')
    def exchange_rates(currency):
        ...

.. autofunction:: flask_quickstart.decorators.memoize

.. autofunction:: flask_quickstart.decorators.ttl_memoize

.. autoclass:: flask_quickstart.decorators.cache.Cache
   :members: make_key

.. autoclass:: flask_quickstart.decorators.cache.TTLFileCache
   :members: load, save, delete, expire, clear

Sentry
~~~~~~

.. autofunction:: flask_quickstart.utils.sentry.setup_sentry

To keep secrets out of Sentry, pass :py:func:`~flask_quickstart.utils.sentry.strip_sensitive_data`
as the ``before_send`` hook:

.. code:: python

    from flask_quickstart.utils.sentry import strip_sensitive_data

    app = create_app(__name__, sentry_kwargs={'before_send': strip_sensitive_data})

.. autofunction:: flask_quickstart.utils.sentry.strip_sensitive_data

.. autofunction:: flask_quickstart.utils.sentry.capture_exception

Zappa
~~~~~

For apps deployed with `Zappa <https://github.com/zappa/Zappa>`__, these can be used as the
``exception_handler`` setting to report exceptions raised outside of Flask, such as during
startup. Tags from a ``package_info.json`` in the working directory are added to the report.

.. code:: json

    {
        "production": {
            "exception_handler": "flask_quickstart.utils.zappa.zappa_handler"
        }
    }

.. autofunction:: flask_quickstart.utils.zappa.zappa_handler

.. autofunction:: flask_quickstart.utils.zappa.capture_exception

Utilities
~~~~~~~~~

.. autofunction:: flask_quickstart.utils.forced_relative_redirect

.. autofunction:: flask_quickstart.utils.str2bool

.. autofunction:: flask_quickstart.utils.random_string
