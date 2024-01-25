"""
Integration with `Sentry, error tracking software <https://sentry.io/welcome/>`_.

In theory, when an exception is raised and not handled, you can use this module
to submit it to your Sentry instance, and track errors produced by your application.

The actual integration is controlled by several environment variables. Each
can be unset, empty or set:

    * ``SENTRY_DSN`` - Client key, or DSN as called by Sentry docs.

      When unset or empty, the integration is disabled and no events are sent to the Sentry server.

    * ``SENTRY_BASE_URL`` - Optional: base URL of your project on the Sentry web server. The module
      can then use this value and construct URLs for reported events, which, when followed, will lead
      to the corresponding issue.

      When unset or empty, such URLs will not be available.

    * ``SENTRY_TAG_MAP`` - Optional: comma-separated mapping between environment variables and additional
      tags, which are attached to every reported event. E.g. ``username=USER,hostname=HOSTNAME`` will add
      2 tags, ``username`` and ``hostname``, setting their values according to the environment. Unset variables
      are silently ignored.

      When unset or empty, no additional tags are added to events.

The actual names of these variables can be changed when creating an instance of
:py:class:`gluetool.sentry.Sentry`.
"""

import os

import sentry_sdk
import sentry_sdk.integrations.argv
import sentry_sdk.integrations.atexit
import sentry_sdk.integrations.dedupe
import sentry_sdk.integrations.excepthook
import sentry_sdk.integrations.logging
import sentry_sdk.integrations.modules
import sentry_sdk.integrations.stdlib
import sentry_sdk.integrations.threading

from six import iteritems

import gluetool
import gluetool.log
import gluetool.utils

# Type annotations
# pylint: disable=unused-import, wrong-import-order
from typing import Any, Dict, Optional, Union  # noqa

import logging  # noqa


class Sentry(object):
    """
    Provides unified interface to the Sentry client, Raven. Callers don't have to think
    whether the submitting is enabled or not, and we can add common tags and other bits
    we'd like to track for all events.

    :param str dsn_env_var: Name of environment variable setting Sentry DSN. Set to ``None``
        to explicitly disable Sentry integration.
    :param str base_url_env_var: Name of environment variable setting base URL of Sentry
        server. Setting to ``None`` will cause the per-event links will not be available
        to users of this class.
    :param str tags_map_env_var: Name of environment variable setting mapping between environment
        variables and additional tags. Set to ``None`` to disable adding these tags.
    """

    def __init__(self,
                 dsn_env_var: Optional[str] = 'SENTRY_DSN',
                 base_url_env_var: Optional[str] = 'SENTRY_BASE_URL',
                 event_url_template_env_var: Optional[str] = 'SENTRY_EVENT_URL_TEMPLATE',
                 tags_map_env_var: Optional[str] = 'SENTRY_TAG_MAP') -> None:

        self._client = None
        self._base_url = None

        if base_url_env_var:
            self._base_url = os.environ.get(base_url_env_var, None)

        if event_url_template_env_var:
            self._event_url_template = os.environ.get(event_url_template_env_var, None)

        self._tag_map: Dict[str, str] = {}

        if tags_map_env_var and os.environ.get(tags_map_env_var):
            try:
                for pair in os.environ[tags_map_env_var].split(','):
                    tag, env_var = pair.split('=')
                    self._tag_map[env_var.strip()] = tag.strip()

            except ValueError as exc:
                raise gluetool.glue.GlueError(
                    'Cannot parse content of {} environment variable'.format(tags_map_env_var)
                ) from exc

        if not dsn_env_var:
            return

        dsn = os.environ.get(dsn_env_var, None)

        if not dsn:
            return

        # Controls how many variables and other items are captured in event and stack frames. The default
        # value of 10 is pretty small, 1000 should be more than enough for anything we ever encounter.
        sentry_sdk.serializer.MAX_DATABAG_BREADTH = 1000

        self._client = sentry_sdk.init(
            dsn=dsn,
            # log all issues
            sample_rate=1.0,
            traces_sample_rate=1.0,
            # We need to override one parameter of on of the default integrations,
            # so we're doomed to list all of them.
            integrations=[
                # Disable sending any log messages as standalone events
                sentry_sdk.integrations.logging.LoggingIntegration(event_level=None),
                # The rest is just default list of integrations.
                # https://docs.sentry.io/platforms/python/configuration/integrations/default-integrations/
                sentry_sdk.integrations.stdlib.StdlibIntegration(),
                sentry_sdk.integrations.excepthook.ExcepthookIntegration(),
                sentry_sdk.integrations.dedupe.DedupeIntegration(),
                sentry_sdk.integrations.atexit.AtexitIntegration(),
                sentry_sdk.integrations.modules.ModulesIntegration(),
                sentry_sdk.integrations.argv.ArgvIntegration(),
                sentry_sdk.integrations.threading.ThreadingIntegration()
            ]

        )

        # Enrich Sentry context with information that are important for us
        context = {}

        # env variables
        for name, value in iteritems(os.environ):
            context['env.{}'.format(name)] = value

        sentry_sdk.set_context('context', context)

    @gluetool.utils.cached_property
    def enabled(self) -> bool:

        return self._client is not None

    def event_url(self, event_id: str, logger: Optional[gluetool.log.ContextAdapter] = None) -> Optional[str]:

        """
        Return URL showing the event on the Sentry server. If ``event_id``
        is ``None`` or when base URL of the Sentry server was not set, ``None``
        is returned instead.

        :param str event_id: ID of the Sentry event, e.g. the one returned by
            :py:meth:`submit_exception` or :py:meth:`submit_warning`.
        :param gluetool.log.ContextAdapter logger: logger to use for logging.
        """

        if self._event_url_template:
            try:
                event_url = gluetool.utils.render_template(
                    self._event_url_template,
                    logger=logger,
                    EVENT_ID=event_id
                )

            except gluetool.GlueError as exc:
                if logger:
                    logger.warning(f"Could not render Sentry event URL template: {exc}")

                return None

            return gluetool.utils.treat_url(event_url, logger=logger)

        if self._base_url:
            return gluetool.utils.treat_url('{}/?query={}'.format(self._base_url, event_id), logger=logger)

        return None

    @staticmethod
    def log_issue(failure: Optional[gluetool.glue.Failure],
                  logger: Optional[gluetool.log.ContextAdapter] = None) -> None:

        """
        Nicely log issue and possibly its URL.

        :param gluetool.glue.Failure failure: ``Failure`` instance describing the exception.
        :param gluetool.log.ContextAdapter logger: logger to use for logging.
        """

        if not logger or not failure:
            return

        logger.error("Submitted as Sentry issue '{}'".format(failure.sentry_event_id))

        if failure.sentry_event_url:
            logger.error('See {} for details.'.format(failure.sentry_event_url))

    def _capture(self,
                 event_type: str,
                 logger: Optional[gluetool.log.ContextAdapter] = None,
                 failure: Optional[gluetool.glue.Failure] = None,
                 **kwargs: Any) -> Optional[str]:

        """
        Prepare common arguments, and then submit the data to the Sentry server.
        """

        #
        # After this line, we CANNOT log with `sentry=True`!
        #
        # This function might have been called by logger's method, e.g. logger.warn(..., sentry=True),
        # if we'd log with sentry=True, we'd use the same logger, getting into possibly infinite recursion.
        #

        tags = kwargs.pop('tags', {})
        fingerprint = kwargs.pop('fingerprint', ['{{ default }}'])

        for env_var, tag in iteritems(self._tag_map):
            if env_var not in os.environ:
                continue

            tags[tag] = os.environ[env_var]

        if failure is not None:
            if 'soft-error' not in tags:
                tags['soft-error'] = failure.soft is True

            if 'exc_info' not in kwargs:
                kwargs['exc_info'] = failure.exc_info

            if hasattr(failure.exception, 'sentry_fingerprint'):
                fingerprint = failure.exception.sentry_fingerprint(fingerprint)  # type: ignore  # has no attribute

            if hasattr(failure.exception, 'sentry_tags'):
                tags = failure.exception.sentry_tags(tags)  # type: ignore  # has no attribute

        with sentry_sdk.push_scope() as scope:
            for tag_key, tag_value in tags.items():
                if tag_value:
                    scope.set_tag(tag_key, tag_value)

            if event_type == 'message':
                event_id = sentry_sdk.capture_message(fingerprint=fingerprint, **kwargs)
            elif event_type == 'exception' and failure:
                event_id = sentry_sdk.capture_exception(error=failure.exc_info, fingerprint=fingerprint)
            else:
                raise gluetool.glue.GlueError('The {} event_type is unknown'.format(event_type))

        if failure is not None:
            failure.sentry_event_id = event_id
            if event_id and self.event_url(event_id, logger=logger):
                failure.sentry_event_url = self.event_url(event_id, logger=logger)

        self.log_issue(failure, logger=logger)

        return event_id

    def submit_exception(self,
                         failure: gluetool.glue.Failure,
                         logger: Optional[gluetool.log.ContextAdapter] = None,
                         **kwargs: Any) -> Optional[str]:

        """
        Submits an exception to the Sentry server. Exceptions are usually submitted
        automagically, but sometimes you might feel the need to share arbitrary issues
        with the world.

        When submitting is not enabled, this method simply returns without sending anything anywhere.

        :param gluetool.glue.Failure failure: ``Failure`` instance describing the exception.
        :param dict kwargs: Additional arguments that will be passed to Sentry's ``captureException``
            method.
        """

        if not self.enabled:
            return None

        exc = failure.exception
        if exc and not getattr(exc, 'submit_to_sentry', True):
            if logger:
                logger.warning('As requested, exception {} not submitted to Sentry'.format(exc.__class__.__name__))

            return None

        return self._capture('exception', logger=logger, failure=failure, **kwargs)

    def submit_message(self,
                       msg: str,
                       logger: Optional[gluetool.log.ContextAdapter] = None,
                       **kwargs: Any) -> Optional[str]:

        """
        Submits a message to the Sentry server. You might feel the need to share arbitrary
        issues - e.g. warnings that are not serious enough to kill the pipeline - with the
        world.

        When submitting is not enabled, this method simply returns without sending anything anywhere.

        :param str msg: Message describing the issue.
        :param dict kwargs: additional arguments that will be passed to Sentry's ``captureMessage``
            method.
        """

        if not self.enabled:
            return None

        return self._capture('message', logger=logger, message=msg, **kwargs)
