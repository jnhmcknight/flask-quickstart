# -*- coding: utf-8 -*-

import json
import os
import logging
import random
import re
import string

from dynaconf import FlaskDynaconf
from flask import Flask, abort, request, redirect, Response, jsonify
from flask_cors import CORS
from flask_cors.core import probably_regex, try_match_any
from flask_csp import CSP
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


def create_app(name, *, log_level=logging.WARN, flask_kwargs=None, sentry_kwargs=None):

    if flask_kwargs is None:
        flask_kwargs = {}

    app = Flask(name, **flask_kwargs)

    FlaskDynaconf(app)

    app.url_map.converters['date'] = DateConverter

    app.logger.setLevel(log_level)
    app.logger.propagate = True

    # Set env var for use in Sentry and other various plugins
    if not app.config.get('ENV'):
        app.config.ENV = os.environ.get(
            'FLASK_ENV', os.environ.get('ENV_FOR_DYNACONF', 'development')
        )

    if sentry_kwargs is None:
        sentry_kwargs = {}

    setup_sentry(app.config, debug=app.debug, **sentry_kwargs)


    logging.getLogger('boto3').setLevel(app.config.get('BOTO3_LOG_LEVEL', logging.CRITICAL))
    logging.getLogger('botocore').setLevel(app.config.get('BOTOCORE_LOG_LEVEL', logging.CRITICAL))
    logging.getLogger('sentry').setLevel(app.config.get('SENTRY_LOG_LEVEL', logging.CRITICAL))
    logging.getLogger('sqlalchemy.engine').setLevel(app.config.get('SQLALCHEMY_LOG_LEVEL', logging.CRITICAL))

    allowed_origins = origins_list_to_regex(app.config.get('ALLOWED_ORIGINS', ['.*']))
    CORS(app, origins=allowed_origins, supports_credentials=True)
    CSP(app)

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
                        not try_match_any(origin, app.allowed_origins) and
                        not try_match_any(f'{origin}/', app.allowed_origins)
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
