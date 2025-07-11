# -*- coding: utf-8 -*-

import json
import os
import logging
import random
import re
import string
import time

from dynaconf import FlaskDynaconf
from flask import Flask, abort, request, redirect, Response, jsonify

try:
    from flask_cors import CORS
    from flask_cors.core import probably_regex, try_match_any_pattern
    FLASK_CORS_IMPORT_ERROR = None
except ImportError as exc:
    FLASK_CORS_IMPORT_ERROR = exc

try:
    from flask_csp import CSP
    FLASK_CSP_IMPORT_ERROR = None
except ImportError as exc:
    FLASK_CSP_IMPORT_ERROR = exc

from werkzeug.middleware.proxy_fix import ProxyFix

from .converters import DateConverter
from .lib.json import ExtendedEncoder
from .utils import forced_relative_redirect
from .utils.sentry import setup_sentry


def origins_list_to_regex(origins):
    logging.info(f'Original origins list: {origins}')
    if not isinstance(origins, (list, set, tuple,)):
        if isinstance(origins, str) and origins.startswith('[') and origins.endswith(']'):
            origins = json.loads(origins)
        else:
            origins = [origins]

    regex_list = []
    for string in origins:
        if not string.startswith('http://') and not string.startswith('https://'):
            string = f'https://{string}'

        if probably_regex(string):
            regex_list.append(re.compile(rf'{string}'))
        else:
            regex_list.append(string)

    return regex_list


def create_app(
    name, *,
    log_level=logging.WARN,
    flask_kwargs=None,
    dynaconf_kwargs=None,
    sentry_kwargs=None,
):

    tries = 0
    app = None
    while app is None:
        tries += 1
        try:
            app = _create_app(
                name,
                log_level=log_level,
                flask_kwargs=flask_kwargs,
                dynaconf_kwargs=dynaconf_kwargs,
                sentry_kwargs=sentry_kwargs,
            )
        except Exception as exc:
            logging.exception(exc)

            if tries >= 5:
                logging.critical('Number of allowed app instantiation retries has been exceeded.')
                raise exc

            time.sleep(random.randint(1,3))
            app = None

    return app


def _create_app(
    name, *,
    log_level=logging.WARN,
    flask_kwargs=None,
    dynaconf_kwargs=None,
    sentry_kwargs=None,
):

    if flask_kwargs is None:
        flask_kwargs = {}

    if dynaconf_kwargs is None:
        dynaconf_kwargs = {
            'extensions': True,
            'LOADERS_FOR_DYNACONF': [
                'dynaconf.loaders.env_loader',
            ],
        }

    elif 'LOADERS_FOR_DYNACONF' in dynaconf_kwargs:
        # We always want to load env vars, so make sure this is here
        if 'dynaconf.loaders.env_loader' not in dynaconf_kwargs['LOADERS_FOR_DYNACONF']:
            dynaconf_kwargs['LOADERS_FOR_DYNACONF'].append('dynaconf.loaders.env_loader')

    if sentry_kwargs is None:
        sentry_kwargs = {}

    app = Flask(name, **flask_kwargs)
    FlaskDynaconf(app, **dynaconf_kwargs)

    app.url_map.converters['date'] = DateConverter

    app.logger.setLevel(log_level)
    app.logger.propagate = True

    # Set env var for use in Sentry and other various plugins
    if not app.config.get('ENV'):
        app.config.ENV = os.environ.get(
            'FLASK_ENV', os.environ.get('ENV_FOR_DYNACONF', 'development')
        )

    setup_sentry(app.config, debug=app.debug, **sentry_kwargs)

    logging.getLogger('boto3').setLevel(app.config.get('BOTO3_LOG_LEVEL', logging.CRITICAL))
    logging.getLogger('botocore').setLevel(app.config.get('BOTOCORE_LOG_LEVEL', logging.CRITICAL))
    logging.getLogger('sentry').setLevel(app.config.get('SENTRY_LOG_LEVEL', logging.CRITICAL))
    logging.getLogger('sqlalchemy.engine').setLevel(app.config.get('SQLALCHEMY_LOG_LEVEL', logging.CRITICAL))

    if FLASK_CORS_IMPORT_ERROR is None:
        allowed_origins = origins_list_to_regex(app.config.get('ALLOWED_ORIGINS', ['.*']))
        CORS(app, origins=allowed_origins, supports_credentials=True)
    else:
        app.logger.warning('Flask-CORS failed to import:')
        app.logger.exception(FLASK_CORS_IMPORT_ERROR)

    if FLASK_CSP_IMPORT_ERROR is None:
        CSP(app)
    else:
        app.logger.warning('Flask-CSP failed to import:')
        app.logger.exception(FLASK_CSP_IMPORT_ERROR)

    app.json_encoder = ExtendedEncoder

    if app.config.get('NUM_PROXIES'):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config.NUM_PROXIES,
            x_proto=app.config.NUM_PROXIES,
            x_host=app.config.NUM_PROXIES,
        )

    if app.config.get('SHORTCIRCUIT_OPTIONS', False):

        def is_allowed_origin():
            if app.allowed_origins:
                origin = request.headers.get('Origin')

                if not origin:
                    app.logger.debug('Origin header not provided')
                    return False

                if (
                        not try_match_any_pattern(origin, app.allowed_origins, caseSensitive=False) and
                        not try_match_any_pattern(f'{origin}/', app.allowed_origins, caseSensitive=False)
                ):
                    app.logger.debug('Origin header not in allowed list: {}'.format(origin))
                    return False

            return True

        @app.before_request
        def chk_shortcircuit():
            if request.method == 'OPTION':
                app.logger.debug('Shortcircuiting OPTIONS request')
                if is_allowed_origin():
                    return '', 200
                return abort(403)

            # If we get here, we're neither shortcircuiting OPTIONS requests, let the view
            # deal with it directly.
            return None

    if app.config.get('RELATIVE_REDIRECTS', False):
        app.url_map.strict_slashes = False

        @app.before_request
        def clear_trailing():
            rp = request.path
            if rp != '/' and rp.endswith('/'):
                return forced_relative_redirect(rp[:-1], code=302)

    if app.config.get('ADD_CACHE_HEADERS', False):

        @app.after_request
        def add_cache_headers(response):
            if response.status_code != 200:
                return response

            content_type = response.headers.get('Content-Type')
            if 'text' in content_type or 'application' in content_type:
                return response

            if not response.headers.get('Cache-Control'):
                response.headers['Cache-Control'] = 'public,max-age=2592000,s-maxage=2592000,immutable'
            if not response.headers.get('Vary'):
                response.headers['Vary'] = 'Accept-Encoding,Origin,Access-Control-Request-Headers,Access-Control-Request-Method'

            return response

    return app
