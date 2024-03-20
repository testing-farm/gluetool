# -*- coding: utf-8 -*-
# pylint: disable=blacklisted-name

import logging
import os
import re
import signal
import subprocess

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
    assert tool.gluetool_config_paths == [
        os.path.join(os.getcwd(), path) for path in ('path1', 'path2', 'path3')
    ]


@pytest.mark.parametrize(
    'tested_signal,exception,terminate_process_tree,excmsg,warnmsg',
    [
        (
            signal.SIGINT,
            KeyboardInterrupt,
            ['sh'],
            '',
            'Interrupted by SIGINT (Ctrl+C?)'
        ),
        (
            signal.SIGINT,
            KeyboardInterrupt,
            [],
            '',
            'Interrupted by SIGINT (Ctrl+C?)'
        ),
        (
            signal.SIGTERM,
            KeyboardInterrupt,
            ['sh'],
            '',
            'Interrupted by SIGTERM'
        ),
        (
            signal.SIGUSR1,
            gluetool.GlueError,
            ['sh'],
            'Pipeline timeout expired',
            'Signal SIGUSR1 received',
        ),
    ],
    ids=['SIGINT', 'SIGINT-no-process-tree', 'SIGTERM', 'SIGUSR1']
)
def test_signal(monkeypatch, log, tested_signal, exception, terminate_process_tree, excmsg, warnmsg):
    tool = gluetool.tool.Gluetool()

    os.environ['GLUETOOL_TRACING_DISABLE'] = '1'

    def mocked_option(_, option):
        if option == 'version':
            return 'some-version'
        if option == 'pipeline':
            return []
        if option == 'terminate-process-tree':
            return terminate_process_tree

    monkeypatch.setattr(gluetool.Glue, 'option', mocked_option)
    monkeypatch.setattr(gluetool.Glue, '_parse_args', MagicMock())

    orig_signal_handler = signal.getsignal(tested_signal)

    with pytest.raises(SystemExit, match='^0$'):
        tool.setup()

    signal_handler = signal.getsignal(tested_signal)

    # run a background process which ignores SIGTERM to test the SIGUSR1 handling
    gluetool.tool.DEFAULT_SIGTERM_TIMEOUT = 0

    process = subprocess.Popen(
        ['sleep 30 & sleep 40'],
        preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_IGN),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        shell=True
    )

    with pytest.raises(exception, match=excmsg):
        signal_handler(tested_signal, MagicMock)

    # restore original signal handler, so we start correctly
    # for the next test
    signal.signal(tested_signal, orig_signal_handler)

    # Wait for the process to terminate
    process.wait()

    # The pipeline_cancelled flad should be set
    assert tool.Glue.pipeline_cancelled is True

    # Note that:
    # * we cannot match concrete order of records
    # * shell process can die before we send SIGKILL to it
    # * we expect that at least one sleep command receives both signals
    # * log.match can match whole strings only, and we have no idea what the PID of sleep processes will be
    assert log.match(levelno=logging.WARNING, message="Sending SIGTERM to child process 'sh' (PID {})".format(process.pid))

    sleep_sigterm = any(
            True
            for record in log.records
            if re.match(
                r"Sending SIGTERM to (?:grand)?child process 'sleep'.*",
                record.message
            ) and record.levelno == logging.WARNING
        )
    sleep_sigkill = any(
            True
            for record in log.records
            if re.match(
                r"Sending SIGKILL to (?:grand)?child process 'sleep'.*",
                record.message
            ) and record.levelno == logging.WARNING
        )

    # sleep should be terminated only if terminate_process_tree set, because it is a child process of `sh`
    if terminate_process_tree:
        assert sleep_sigterm
        assert sleep_sigkill
    else:
        assert not sleep_sigterm
        assert not sleep_sigkill

    assert log.match(levelno=logging.WARNING, message=warnmsg)
    assert log.match(levelno=logging.DEBUG, message='Exiting with status 0')
    assert log.match(levelno=logging.INFO, message='gluetool some-version')
