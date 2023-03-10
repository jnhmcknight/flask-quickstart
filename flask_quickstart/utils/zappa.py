
import sentry_sdk

from .sentry import setup_sentry


def zappa_handler(e, event, context):
    "Exception handler reports exceptions to sentry but does not capture them."

    setup_sentry()

    with sentry_sdk.configure_scope() as scope:
        scope.set_tag('handler', 'raw-zappa')

        try:
            package_info_file = open('package_info.json', 'r')
            package_info = json.load(package_info_file)
            package_info_file.close()

            for key, value in package_info.items():
                scope.set_tag(key, value)

        except OSError:
            # not deployed, probably a test
            pass

        if 'httpMethod' in event:
            scope.set_tag('http_method', event['httpMethod'])
            scope.set_tag('path', event['path'])

        if 'headers' in event:
            if 'Host' in event['headers']:
                scope.set_tag('host', event['headers']['Host'])
            if 'User-Agent' in event['headers']:
                scope.set_tag('user_agent', event['headers']['User-Agent'])

        if 'requestContext' in event and 'stage' in event['requestContext']:
            scope.set_tag('stage', event['requestContext']['stage'])

        scope.set_extra('event', event)

    sentry_sdk.capture_exception(e)
    return False


def capture_exception(e, event, context):
    "Exception handler that makes exceptions disappear after processing them."

    zappa_handler(e, event, context)
    return True
