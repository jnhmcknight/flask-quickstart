Configuration
=============

Loading settings
~~~~~~~~~~~~~~~~

:py:func:`~flask_quickstart.create_app` loads the app's config with Dynaconf's
`Flask extension <https://www.dynaconf.com/flask/>`__. Settings come from, in increasing order of
precedence:

   #. A ``settings.toml`` file in the working directory
   #. Environment variables prefixed with ``FLASK_``

The settings file has a section per environment, plus a ``[default]`` section that applies to all
of them. ``FLASK_ENV`` (or ``ENV_FOR_DYNACONF``) selects the environment, and defaults to
``development``:

.. code:: toml

    [default]
    ALLOWED_ORIGINS = ['example.com']
    ADD_CACHE_HEADERS = true

    [production]
    SENTRY_DSN = 'https://key@o0.ingest.sentry.io/0'

Environment variable values are parsed as TOML, so booleans, numbers and lists can be given
directly::

    FLASK_ADD_CACHE_HEADERS=false
    FLASK_NUM_PROXIES=1
    FLASK_ALLOWED_ORIGINS='["example.com", "www.example.com"]'

To load settings some other way, pass Dynaconf options as ``dynaconf_kwargs``. The environment
variable loader is always kept:

.. code:: python

    app = create_app(__name__, dynaconf_kwargs={'settings_files': ['config/settings.toml']})

Settings are available as ``app.config['NAME']`` or ``app.config.NAME``.

Environment
~~~~~~~~~~~

``ENV`` (:py:class:`str`)
   The name of the environment, e.g. ``production``. Taken from the ``FLASK_ENV`` or
   ``ENV_FOR_DYNACONF`` environment variables when not set, and defaults to ``development``.
   Sentry is not set up in the ``development`` and ``testing`` environments.

CORS
~~~~

CORS is handled by `Flask-CORS <https://flask-cors.readthedocs.io/>`__ when it is installed (the
``cors`` extra). Credentials are always allowed.

``ALLOWED_ORIGINS`` (:py:class:`list` of :py:class:`str`)
   The origins allowed to make cross-origin requests. Each is either an exact origin or a regular
   expression, which is assumed for anything containing one of ``*\]?$^[]()``. Origins without a
   scheme are given ``https://``, and matching ignores case.

   Defaults to ``['.*']``, which allows every HTTPS origin.

   .. code:: toml

      ALLOWED_ORIGINS = [
          'example.com',                     # only https://example.com
          'http://localhost:3000',
          '.*\.example\.com$',               # any subdomain of example.com
      ]

   .. warning::

      Regular expressions are matched against the start of the origin only. Without a trailing
      ``$``, ``.*\.example\.com`` also allows ``https://www.example.com.attacker.net``. Since
      credentials are allowed, end every pattern with ``$``.

Other `Flask-CORS options <https://flask-cors.readthedocs.io/en/latest/configuration.html>`__ can
be set with its ``CORS_*`` settings, except ``CORS_ORIGINS`` and ``CORS_SUPPORTS_CREDENTIALS``,
which are always overridden.

``SHORTCIRCUIT_OPTIONS`` (:py:class:`bool`)
   Answer every ``OPTIONS`` request before it reaches a view: with an empty ``200`` response when
   its ``Origin`` header is in ``ALLOWED_ORIGINS``, and ``403`` otherwise, including when it has
   no ``Origin`` header. Defaults to ``False``.

Content Security Policy
~~~~~~~~~~~~~~~~~~~~~~~

When `Flask-CSP <https://github.com/fictive-kin/flask-csp>`__ is installed (the ``csp`` extra), a
``Content-Security-Policy`` header is added to every response. Without any settings, the policy is
``default-src 'self'``, which blocks resources from other origins.

The policy is configured with ``CSP_*`` settings, one per directive, plus ``CSP_REPORT_ONLY``:

.. code:: toml

    CSP_DEFAULT_SRC = ['https:', 'self']
    CSP_IMG_SRC = ['self', 'data:']
    CSP_UPGRADE_INSECURE_REQUESTS = true

produces::

    Content-Security-Policy: default-src https: 'self'; img-src 'self' data:; upgrade-insecure-requests

See the `Flask-CSP configuration docs
<https://github.com/fictive-kin/flask-csp/blob/main/docs/configuration.rst>`__ for every
directive and option.

Sentry
~~~~~~

When sentry-sdk is installed (the ``sentry`` extra), errors are reported to Sentry, with the Flask
and Boto3 integrations enabled and 10% of requests traced. See
:py:func:`~flask_quickstart.utils.sentry.setup_sentry`, which ``create_app`` passes its
``sentry_kwargs`` to.

``SENTRY_DSN`` (:py:class:`str`)
   The DSN to report to. Falls back to the ``SENTRY_DSN`` or ``FLASK_SENTRY_DSN`` environment
   variables. Sentry is not set up without one.

Requests and responses
~~~~~~~~~~~~~~~~~~~~~~

``NUM_PROXIES`` (:py:class:`int`)
   The number of proxies in front of the app. When set, the client address, scheme and host are
   taken from the ``X-Forwarded-For``, ``X-Forwarded-Proto`` and ``X-Forwarded-Host`` headers
   using Werkzeug's :py:class:`~werkzeug.middleware.proxy_fix.ProxyFix`. Only set this when the
   app is behind proxies that set those headers, since clients can otherwise forge them.

``RELATIVE_REDIRECTS`` (:py:class:`bool`)
   Redirect any path ending in a slash to the same path without it, e.g. ``/about/`` to
   ``/about``, using a ``302`` with a relative ``Location`` header. The query string is not
   kept. Defaults to ``False``.

``ADD_CACHE_HEADERS`` (:py:class:`bool`)
   Make browsers and CDNs cache successful responses for files such as images, fonts, audio and
   video for 30 days. Applies to ``200`` responses whose ``Content-Type`` contains neither
   ``text`` nor ``application``, and adds these headers when they are not already set::

      Cache-Control: public,max-age=2592000,s-maxage=2592000,immutable
      Vary: Accept-Encoding,Origin,Access-Control-Request-Headers,Access-Control-Request-Method

   Defaults to ``False``.

Caching
~~~~~~~

These settings are used by :py:func:`~flask_quickstart.decorators.ttl_memoize`.

``CACHE_STORAGE_FOLDER`` (:py:class:`str`)
   The folder to store cached values in. Nothing is cached when this is not set.

``CACHE_TTL`` (:py:class:`int`)
   How many seconds values are cached for, unless the decorator sets its own. Defaults to
   ``900``.

Logging
~~~~~~~

These set the level of noisy third-party loggers. Each takes a :py:mod:`logging` level, either
as a number or a name such as ``'INFO'``, and defaults to ``CRITICAL``.

* ``BOTO3_LOG_LEVEL``
* ``BOTOCORE_LOG_LEVEL``
* ``SENTRY_LOG_LEVEL``
* ``SQLALCHEMY_LOG_LEVEL``, for the ``sqlalchemy.engine`` logger

The app's own logger level is set with the ``log_level`` argument to
:py:func:`~flask_quickstart.create_app`.
