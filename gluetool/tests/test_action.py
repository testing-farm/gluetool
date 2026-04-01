import os

import pytest
from unittest.mock import patch, MagicMock

import gluetool.action
from gluetool.action import (
    TRACING_INSECURE_ENVVAR,
    TRACING_TLS_CERT_ENVVAR,
    Tracer,
)


@pytest.fixture(autouse=True)
def _reset_tracer():
    """Reset Tracer class state between tests."""
    Tracer.TRACER = None
    Tracer._PROVIDER = None
    yield
    Tracer.TRACER = None
    Tracer._PROVIDER = None


@pytest.fixture()
def mock_otel():
    """Mock all OpenTelemetry objects used by Tracer.__init__."""
    with patch.object(gluetool.action, 'HAS_TRACING', True), \
         patch.object(gluetool.action, 'Resource'), \
         patch.object(gluetool.action, 'TracerProvider'), \
         patch.object(gluetool.action, 'BatchSpanProcessor'), \
         patch.object(gluetool.action, 'OTLPSpanExporter') as mock_exporter_cls, \
         patch.object(gluetool.action, 'trace'), \
         patch.object(gluetool.action, 'grpc', create=True) as mock_grpc:
        yield {
            'exporter_cls': mock_exporter_cls,
            'grpc': mock_grpc,
        }


@pytest.mark.parametrize('env_value', [
    '',      # not set
    'true',
    'yes',
    '1',
    'anything',
])
def test_insecure_by_default(env_value, mock_otel):
    """Connection is insecure when GLUETOOL_TRACING_INSECURE is unset or not explicitly disabled."""

    env = {TRACING_INSECURE_ENVVAR: env_value} if env_value else {}

    with patch.dict(os.environ, env, clear=False):
        if not env_value:
            os.environ.pop(TRACING_INSECURE_ENVVAR, None)
        Tracer()

    _, kwargs = mock_otel['exporter_cls'].call_args
    assert kwargs.get('insecure') is True


@pytest.mark.parametrize('env_value', ['0', 'false', 'no', 'False', 'NO', 'No'])
def test_secure_when_insecure_disabled(env_value, mock_otel):
    """Connection uses TLS when GLUETOOL_TRACING_INSECURE is set to 0/false/no."""

    with patch.dict(os.environ, {TRACING_INSECURE_ENVVAR: env_value}, clear=False):
        os.environ.pop(TRACING_TLS_CERT_ENVVAR, None)
        Tracer()

    _, kwargs = mock_otel['exporter_cls'].call_args
    assert 'insecure' not in kwargs
    assert 'credentials' not in kwargs


def test_tls_cert_used_when_secure(mock_otel, tmp_path):
    """Custom CA cert is loaded and passed as gRPC credentials when TLS is enabled."""

    cert_content = b'--- FAKE CA CERT ---'
    cert_file = tmp_path / 'ca.pem'
    cert_file.write_bytes(cert_content)

    mock_creds = MagicMock()
    mock_otel['grpc'].ssl_channel_credentials.return_value = mock_creds

    with patch.dict(os.environ, {
        TRACING_INSECURE_ENVVAR: 'false',
        TRACING_TLS_CERT_ENVVAR: str(cert_file),
    }, clear=False):
        Tracer()

    mock_otel['grpc'].ssl_channel_credentials.assert_called_once_with(root_certificates=cert_content)
    _, kwargs = mock_otel['exporter_cls'].call_args
    assert kwargs.get('credentials') is mock_creds


def test_tls_cert_ignored_when_insecure(mock_otel, tmp_path):
    """GLUETOOL_TRACING_TLS_CERT is ignored when connection is insecure."""

    cert_file = tmp_path / 'ca.pem'
    cert_file.write_bytes(b'--- FAKE CA CERT ---')

    with patch.dict(os.environ, {
        TRACING_TLS_CERT_ENVVAR: str(cert_file),
    }, clear=False):
        os.environ.pop(TRACING_INSECURE_ENVVAR, None)
        Tracer()

    mock_otel['grpc'].ssl_channel_credentials.assert_not_called()
    _, kwargs = mock_otel['exporter_cls'].call_args
    assert kwargs.get('insecure') is True
