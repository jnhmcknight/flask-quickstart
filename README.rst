Flask-Quickstart
================

A quick start for commonly used features of a Flask app. A single call to ``create_app`` gives you
a Flask app with:

- configuration loaded by `Dynaconf <https://www.dynaconf.com/>`__ from ``settings.toml`` and
  ``FLASK_*`` environment variables
- CORS, with the allowed origins set from config
- a Content-Security-Policy header, via `Flask-CSP <https://github.com/fictive-kin/flask-csp>`__
- Sentry error reporting
- JSON responses that handle dates, datetimes, UUIDs, enums, sets and dataclasses
- a ``date`` URL converter
- optional proxy header handling, cache headers, trailing-slash redirects and ``OPTIONS``
  short-circuiting

Requires Python 3.10+ and Flask 3.


Installation
------------

.. code:: bash

    $ pip install "flask-quickstart[full] @ git+https://github.com/jnhmcknight/flask-quickstart.git"

The ``full`` extra installs everything. To pick features individually, use the ``cors``, ``csp``
and ``sentry`` extras instead; any feature whose package isn't installed is skipped.

The ``csp`` extra installs `fictive-kin/flask-csp <https://github.com/fictive-kin/flask-csp>`__
from git, not the unrelated ``flask-csp`` package on PyPI.


Quick start
-----------

.. code:: python

    from flask_quickstart import create_app

    app = create_app(__name__)

    @app.route('/')
    def index():
        return {'hello': 'world'}

Settings are read from a ``settings.toml`` in the working directory, with one section per
environment:

.. code:: toml

    [default]
    # Sets the allowed origins for CORS
    ALLOWED_ORIGINS = ['example.com', 'www.example.com']

    # Default CSP policy that we want in place
    CSP_DEFAULT_SRC = ['https:', 'self']
    CSP_UPGRADE_INSECURE_REQUESTS = true

    [production]
    SENTRY_DSN = 'https://key@o0.ingest.sentry.io/0'

``FLASK_ENV`` selects the environment, and any setting can be overridden with an environment
variable prefixed with ``FLASK_``, e.g. ``FLASK_ALLOWED_ORIGINS='["example.com"]'``.

See the documentation for every setting and the rest of the API.


Development
-----------

.. code:: bash

    $ pip install -e ".[tests,lint,docs]"
    $ pytest
    $ ruff check . && ruff format --check .
    $ make -C docs html
