from __future__ import annotations

import pytest

from src.common.errors import ConfigurationError
from src.connectors.oracle import OracleConnector

PROFILE = {
    "connection": {
        "dsn_env": "TEST_ORACLE_DSN",
        "host_env": "TEST_ORACLE_HOST",
        "port_env": "TEST_ORACLE_PORT",
        "service_name_env": "TEST_ORACLE_SERVICE",
        "sid_env": "TEST_ORACLE_SID",
        "user_env": "TEST_ORACLE_USER",
        "password_env": "TEST_ORACLE_PASSWORD",
        "thick_mode_env": "TEST_ORACLE_THICK_MODE",
        "thick_mode_client_env": "TEST_ORACLE_CLIENT_LIB_DIR",
    },
    "oracle": {"arraysize": 500},
}

_ENV_NAMES = [
    "TEST_ORACLE_DSN", "TEST_ORACLE_HOST", "TEST_ORACLE_PORT",
    "TEST_ORACLE_SERVICE", "TEST_ORACLE_SID", "TEST_ORACLE_THICK_MODE",
    "TEST_ORACLE_CLIENT_LIB_DIR", "TEST_ORACLE_USER", "TEST_ORACLE_PASSWORD",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TEST_ORACLE_USER", "PBI_JDE")
    monkeypatch.setenv("TEST_ORACLE_PASSWORD", "super-secret-value")
    yield


def test_dsn_uses_sid_when_no_service_or_dsn(monkeypatch):
    monkeypatch.setenv("TEST_ORACLE_HOST", "192.168.1.200")
    monkeypatch.setenv("TEST_ORACLE_PORT", "1521")
    monkeypatch.setenv("TEST_ORACLE_SID", "JDEVM")

    connector = OracleConnector(PROFILE)

    assert connector.connection_mode == "SID"
    assert "JDEVM" in connector.dsn
    assert connector.driver_mode == "THIN"


def test_dsn_priority_prefers_explicit_dsn(monkeypatch):
    monkeypatch.setenv("TEST_ORACLE_DSN", "custom-tns-descriptor")
    monkeypatch.setenv("TEST_ORACLE_HOST", "192.168.1.200")
    monkeypatch.setenv("TEST_ORACLE_PORT", "1521")
    monkeypatch.setenv("TEST_ORACLE_SID", "JDEVM")
    monkeypatch.setenv("TEST_ORACLE_SERVICE", "JDEPROD")

    connector = OracleConnector(PROFILE)

    assert connector.connection_mode == "DSN"
    assert connector.dsn == "custom-tns-descriptor"


def test_dsn_prefers_service_over_sid(monkeypatch):
    monkeypatch.setenv("TEST_ORACLE_HOST", "192.168.1.200")
    monkeypatch.setenv("TEST_ORACLE_PORT", "1521")
    monkeypatch.setenv("TEST_ORACLE_SID", "JDEVM")
    monkeypatch.setenv("TEST_ORACLE_SERVICE", "JDEPROD")

    connector = OracleConnector(PROFILE)

    assert connector.connection_mode == "SERVICE_NAME"


def test_missing_connection_target_raises_configuration_error():
    with pytest.raises(ConfigurationError):
        OracleConnector(PROFILE)


def test_thin_mode_by_default(monkeypatch):
    monkeypatch.setenv("TEST_ORACLE_HOST", "192.168.1.200")
    monkeypatch.setenv("TEST_ORACLE_PORT", "1521")
    monkeypatch.setenv("TEST_ORACLE_SID", "JDEVM")

    connector = OracleConnector(PROFILE)

    assert connector.thick_mode is False
    assert connector.driver_mode == "THIN"


def test_thick_mode_requires_client_dir(monkeypatch):
    monkeypatch.setenv("TEST_ORACLE_HOST", "192.168.1.200")
    monkeypatch.setenv("TEST_ORACLE_PORT", "1521")
    monkeypatch.setenv("TEST_ORACLE_SID", "JDEVM")
    monkeypatch.setenv("TEST_ORACLE_THICK_MODE", "true")

    with pytest.raises(ConfigurationError):
        OracleConnector(PROFILE)


def test_thick_mode_enabled_when_client_dir_present(monkeypatch):
    import oracledb

    monkeypatch.setenv("TEST_ORACLE_HOST", "192.168.1.200")
    monkeypatch.setenv("TEST_ORACLE_PORT", "1521")
    monkeypatch.setenv("TEST_ORACLE_SID", "JDEVM")
    monkeypatch.setenv("TEST_ORACLE_THICK_MODE", "true")
    monkeypatch.setenv("TEST_ORACLE_CLIENT_LIB_DIR", "/opt/oracle/instantclient")

    calls: list[str | None] = []
    monkeypatch.setattr(
        oracledb, "init_oracle_client",
        lambda lib_dir=None: calls.append(lib_dir),
    )

    connector = OracleConnector(PROFILE)

    assert connector.thick_mode is True
    assert connector.driver_mode == "THICK"
    assert calls == ["/opt/oracle/instantclient"]


def test_password_is_not_a_public_attribute(monkeypatch):
    monkeypatch.setenv("TEST_ORACLE_HOST", "192.168.1.200")
    monkeypatch.setenv("TEST_ORACLE_PORT", "1521")
    monkeypatch.setenv("TEST_ORACLE_SID", "JDEVM")

    connector = OracleConnector(PROFILE)

    assert not hasattr(connector, "password")
