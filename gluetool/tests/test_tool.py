# -*- coding: utf-8 -*-
# pylint: disable=blacklisted-name

import logging
import os
import signal

import pkg_resources
import pytest
from mock import MagicMock

import gluetool
import gluetool.tool

from . import NonLoadingGlue


@pytest.fixture(name='tool')
def fixture_gluetool(monkeypatch):
    monkeypatch.setattr(gluetool.glue, 'Glue', NonLoadingGlue)

    return gluetool.tool.Gluetool()


def test_basic(monkeypatch, tool):
    assert tool.gluetool_config_paths == gluetool.tool.DEFAULT_GLUETOOL_CONFIG_PATHS

    monkeypatch.setattr(
        pkg_resources,
        'get_distribution',
        MagicMock(return_value=MagicMock(version='some-version')),
    )
    assert tool._version == 'some-version'


def test_init_environ(monkeypatch):
    os.environ['GLUETOOL_CONFIG_PATHS'] = 'path1,path2,path3'

    monkeypatch.setattr(gluetool.glue, 'Glue', NonLoadingGlue)

    tool = gluetool.tool.Gluetool()
    tool.gluetool_config_paths == ['path1', 'path2', 'path3']


@pytest.mark.parametrize(
    'tested_signal,exception,excmsg,warnmsg',
    [
        (signal.SIGINT, KeyboardInterrupt, '', 'Interrupted by SIGINT (Ctrl+C?)'),
        (signal.SIGTERM, KeyboardInterrupt, '', 'Interrupted by SIGTERM'),
        (
            signal.SIGUSR1,
            gluetool.GlueError,
            'Pipeline timeout expired',
            'Signal SIGUSR1 received',
        ),
    ],
    ids=['SIGINT', 'SIGTERM', 'SIGUSR1']
)
def test_signal(monkeypatch, log, tested_signal, exception, excmsg, warnmsg):
    tool = gluetool.tool.Gluetool()

    os.environ['GLUETOOL_TRACING_DISABLE'] = '1'

    def mocked_option(_, option):
        if option == 'version':
            return 'some-version'
        if option == 'pipeline':
            return []

    monkeypatch.setattr(gluetool.Glue, 'option', mocked_option)
    monkeypatch.setattr(gluetool.Glue, '_parse_args', MagicMock())

    orig_signal_handler = signal.getsignal(tested_signal)

    with pytest.raises(SystemExit, match='^0$'):
        tool.setup()

    signal_handler = signal.getsignal(tested_signal)

    with pytest.raises(exception, match=excmsg):
        signal_handler(tested_signal, MagicMock)

    assert tool.Glue.pipeline_cancelled is True

    assert log.records[-1].message == warnmsg
    assert log.records[-2].message == 'Exiting with status 0'
    assert log.records[-3].message == 'gluetool some-version'

    # restore original signal handler, so we start correctly
    # for the next test
    signal.signal(tested_signal, orig_signal_handler)
