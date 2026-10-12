import sys
import threading

import requests as original_requests
from six.moves import http_client

from mock import MagicMock

from gluetool.utils import requests, _http_client_debugging


METHOD_NAMES = ('head', 'get', 'post', 'put', 'patch', 'delete')

# How long a test thread waits for the other one before giving up.
TIMEOUT = 10


def _run_threads(*targets):
    """
    Run each target in its own thread, wait for all of them to finish, and re-raise the first exception
    any of them raised. ``threading.Thread`` swallows exceptions, failed assertions would get lost otherwise.
    """

    errors = []

    def _wrapper(target):
        try:
            target()

        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    threads = [threading.Thread(target=_wrapper, args=(target,)) for target in targets]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    if errors:
        raise errors[0]


def test_sanity():
    original_methods = {
        method_name: getattr(original_requests, method_name) for method_name in METHOD_NAMES
    }

    with requests() as R:
        assert R.exceptions is original_requests.exceptions
        assert R.Session is original_requests.Session

        # `requests` module must stay untouched, other threads may be using it.
        for method_name in METHOD_NAMES:
            assert getattr(original_requests, method_name) is original_methods[method_name]

    for method_name in METHOD_NAMES:
        assert getattr(original_requests, method_name) is original_methods[method_name]


def test_request_methods(monkeypatch, log):
    for method_name in METHOD_NAMES:
        response = MagicMock(text='{} response'.format(method_name))

        monkeypatch.setattr(original_requests, method_name, MagicMock(return_value=response))

        with requests() as R:
            assert getattr(R, method_name)('https://example.com', timeout=10) is response

        getattr(original_requests, method_name).assert_called_once_with('https://example.com', timeout=10)

        assert any('{} response'.format(method_name) in record.message for record in log.records)


def test_http_client_debugging(log):
    assert http_client.HTTPConnection.debuglevel == 0
    assert not hasattr(http_client, 'print')

    with requests():
        assert http_client.HTTPConnection.debuglevel == 1

        # This is what `http_client` does when debugging is enabled.
        http_client.print('reply:', repr('HTTP/1.1 200 OK\r\n'))

    assert http_client.HTTPConnection.debuglevel == 0
    assert not hasattr(http_client, 'print')

    assert any("reply: 'HTTP/1.1 200 OK\\r\\n'" in record.message for record in log.records)


def test_http_client_debugging_nested():
    outer_logger, inner_logger = MagicMock(), MagicMock()

    with _http_client_debugging(outer_logger):
        with _http_client_debugging(inner_logger):
            http_client.print('header:', 'inner')

        http_client.print('header:', 'outer')

    inner_logger.debug.assert_called_once_with('header: inner')
    outer_logger.debug.assert_called_once_with('header: outer')


def test_http_client_debugging_restores_print(monkeypatch):
    original_print = MagicMock()

    monkeypatch.setattr(http_client, 'print', original_print, raising=False)

    with requests():
        assert http_client.print is not original_print

    assert http_client.print is original_print


def test_http_client_debugging_other_thread(log, capsys):
    def _print_from_other_thread():
        http_client.print('header:', 'from other thread')

    with requests():
        _run_threads(_print_from_other_thread)

    # Output of threads without an active context is dropped, it must not leak to stdout.
    assert not any('from other thread' in record.message for record in log.records)
    assert 'from other thread' not in capsys.readouterr().out


def test_overlapping_threads():
    """
    Two threads with overlapping contexts, the first one to enter leaves first. This used to leave ``sys.stdout``
    replaced by a fake stream, and the interpreter then exited with 120 because it could not flush the stream.
    """

    original_stdout, original_stderr = sys.stdout, sys.stderr

    a_entered, b_entered, a_left = threading.Event(), threading.Event(), threading.Event()
    debuglevels = {}

    def _thread_a():
        with requests():
            a_entered.set()
            assert b_entered.wait(TIMEOUT)

        a_left.set()

    def _thread_b():
        assert a_entered.wait(TIMEOUT)

        with requests():
            b_entered.set()
            assert a_left.wait(TIMEOUT)

            debuglevels['after-a-left'] = http_client.HTTPConnection.debuglevel

    _run_threads(_thread_a, _thread_b)

    # Debugging stays on while any context is active...
    assert debuglevels['after-a-left'] == 1

    # ... and everything is restored once all of them are gone.
    assert http_client.HTTPConnection.debuglevel == 0
    assert not hasattr(http_client, 'print')

    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr
