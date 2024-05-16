import json
import logging
import re
import string

import pytest
from gluetool.tests import CaplogWrapper
from hypothesis import assume, given, strategies as st
from gluetool.help import EVAL_CONTEXT_HELP_TEMPLATE

import gluetool.log
from gluetool.log import ContextAdapter, Topic
from gluetool.result import E

# strategy to generate strctured data
_structured = st.recursive(st.none() | st.booleans() | st.floats(allow_nan=False) | st.text(string.printable),
                           lambda children: st.lists(children) | st.dictionaries(st.text(string.printable), children))


@given(blob=st.text(alphabet=string.printable + string.whitespace))
def test_format_blob(blob):
    pattern = r"""^{}$
{}
^{}$""".format(re.escape(gluetool.log.BLOB_HEADER),
               re.escape(blob),
               re.escape(gluetool.log.BLOB_FOOTER))

    re.match(pattern, gluetool.log.format_blob(blob), re.MULTILINE)


@given(data=_structured)
def test_format_dict(data):
    # This is what format_dict does... I don't have other way to generate similar to output to match format_dict
    # with other code. Therefore this is more like a sanity test, checking that format_dict does some formatting,
    # ignoring how its output actually looks.
    def default(obj):
        return repr(obj)

    expected = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '), default=default)

    assert re.match(re.escape(expected), gluetool.log.format_dict(data), re.MULTILINE)


def generate_topic_testcase(logfn, level, name=''):
    return pytest.param(
        logfn,
        'message',
        Topic.EVAL_CONTEXT if 'eval-context' in name else None,
        [Topic.EVAL_CONTEXT] if 'eval-context-logged' in name else None,
        level,
        None if 'not-logged' in name else 'message',
        id='{}-{}'.format(logfn, name) if name else logfn
    )


@pytest.mark.parametrize('function, msg, topic, topics, level, expected', [
    generate_topic_testcase('verbose', gluetool.log.VERBOSE),
    generate_topic_testcase('verbose', gluetool.log.VERBOSE, 'eval-context-logged'),
    generate_topic_testcase('verbose', gluetool.log.VERBOSE, 'eval-context-not-logged'),
    generate_topic_testcase('debug', logging.DEBUG),
    generate_topic_testcase('debug', logging.DEBUG, 'eval-context-logged'),
    generate_topic_testcase('debug', logging.DEBUG, 'eval-context-not-logged'),
    generate_topic_testcase('info', logging.INFO),
    generate_topic_testcase('info', logging.INFO, 'eval-context-logged'),
    generate_topic_testcase('info', logging.INFO, 'eval-context-not-logged'),
    generate_topic_testcase('warning', logging.WARNING),
    generate_topic_testcase('warning', logging.WARNING, 'eval-context-logged'),
    generate_topic_testcase('warning', logging.WARNING, 'eval-context-not-logged'),
    generate_topic_testcase('error', logging.ERROR),
    generate_topic_testcase('error', logging.ERROR, 'eval-context-logged'),
    generate_topic_testcase('error', logging.ERROR, 'eval-context-not-logged'),
])
def test_log_topics(log, function, msg, topic, topics, level, expected):
    logger = gluetool.log.Logging.setup_logger(topics=topics)

    getattr(logger, function)(msg, topic=topic)

    records = [record for record in log.records if record.levelno == level and record.message == msg]

    if expected:
        assert len(records) == 1
        return

    assert len(records) == 0


@pytest.mark.parametrize('function, msg, topic, topics, level, expected', [
    generate_topic_testcase('verbose', gluetool.log.VERBOSE),
    generate_topic_testcase('verbose', gluetool.log.VERBOSE, 'eval-context-logged'),
    generate_topic_testcase('verbose', gluetool.log.VERBOSE, 'eval-context-not-logged'),
    generate_topic_testcase('debug', logging.DEBUG),
    generate_topic_testcase('debug', logging.DEBUG, 'eval-context-logged'),
    generate_topic_testcase('debug', logging.DEBUG, 'eval-context-not-logged'),
    generate_topic_testcase('info', logging.INFO),
    generate_topic_testcase('info', logging.INFO, 'eval-context-logged'),
    generate_topic_testcase('info', logging.INFO, 'eval-context-not-logged'),
    generate_topic_testcase('warning', logging.WARNING),
    generate_topic_testcase('warning', logging.WARNING, 'eval-context-logged'),
    generate_topic_testcase('warning', logging.WARNING, 'eval-context-not-logged'),
    generate_topic_testcase('error', logging.ERROR),
    generate_topic_testcase('error', logging.ERROR, 'eval-context-logged'),
    generate_topic_testcase('error', logging.ERROR, 'eval-context-not-logged'),
])
def test_log_topics_context_adapter(log, function, msg, topic, topics, level, expected):
    logger_main = gluetool.log.Logging.setup_logger(topics=topics)
    adapter = ContextAdapter(logger=logger_main)
    logger = ContextAdapter(logger=adapter)

    getattr(logger, function)(msg, topic=topic)

    records = [record for record in log.records if record.levelno == level and record.message == msg]

    if expected:
        assert len(records) == 1
        return

    assert len(records) == 0
