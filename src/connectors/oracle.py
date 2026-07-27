from __future__ import annotations

import logging
from typing import Any

import oracledb
import pandas as pd

from src.common.config import env_bool, env_int, env_optional, env_required
from src.common.errors import ConfigurationError, SourceConnectionError
from src.connectors.base import SourceConnector

LOGGER = logging.getLogger(__name__)

# Substring match against str(exception); Oracle error codes are stable
# regardless of oracledb driver version or locale.
_ORACLE_ERROR_HINTS = {
    "ORA-01017": "Invalid username/password; check ORACLE_USER/ORACLE_PASSWORD.",
    "ORA-12154": "TNS could not resolve the connect identifier — check ORACLE_DSN/ORACLE_SERVICE/ORACLE_SID.",
    "ORA-12514": "Listener does not know the requested service name — check ORACLE_SERVICE.",
    "ORA-12541": "No listener at host/port — check ORACLE_HOST/ORACLE_PORT and network reachability.",
    "ORA-00942": "Table or view does not exist or is not granted — check ORACLE_SCHEMA and privileges.",
    "DPY-6005": "Cannot connect using python-oracledb Thin mode; consider ORACLE_THICK_MODE=true with an Instant Client.",
}


def _oracle_error_hint(exc: Exception) -> str | None:
    text = str(exc)
    for code, hint in _ORACLE_ERROR_HINTS.items():
        if code in text:
            return hint
    return None


class OracleConnector(SourceConnector):
    """Oracle connector for python-oracledb.

    DSN resolution priority: ORACLE_DSN (or profile-configured dsn_env) >
    host+port+service_name > host+port+SID. Thin mode is used unless Thick
    mode is explicitly requested and an Instant Client directory is
    configured. The password is read from the environment and is never
    stored on an attribute that could be logged or repr'd accidentally.
    """

    def __init__(self, profile: dict[str, Any]):
        connection = profile["connection"]
        self.user = env_required(connection["user_env"])
        self.__password = env_required(connection["password_env"])
        source_options = profile.get("oracle", {}) or profile.get("jde", {})

        fetch_size_env = source_options.get("fetch_size_env")
        self.arraysize = (
            env_int(fetch_size_env, int(source_options.get("arraysize", 10000)))
            if fetch_size_env
            else int(source_options.get("arraysize", 10000))
        )
        timeout_env = source_options.get("query_timeout_env")
        self.query_timeout_seconds = (
            env_int(timeout_env, 120) if timeout_env else 120
        )

        dsn_env = connection.get("dsn_env")
        explicit_dsn = env_optional(dsn_env) if dsn_env else None

        service_env = connection.get("service_name_env")
        service_name = env_optional(service_env) if service_env else None

        sid_env = connection.get("sid_env")
        sid = env_optional(sid_env) if sid_env else None

        host_env = connection.get("host_env")
        port_env = connection.get("port_env")
        host = env_optional(host_env) if host_env else None
        port = int(env_optional(port_env, "1521") or 1521) if port_env else None

        if explicit_dsn:
            self.dsn = explicit_dsn
            self.connection_mode = "DSN"
        elif host and port and service_name:
            self.dsn = oracledb.makedsn(host, port, service_name=service_name)
            self.connection_mode = "SERVICE_NAME"
        elif host and port and sid:
            self.dsn = oracledb.makedsn(host, port, sid=sid)
            self.connection_mode = "SID"
        else:
            raise ConfigurationError(
                "Oracle connection is not configured: provide ORACLE_DSN, or "
                "host+port with ORACLE_SERVICE, or host+port with ORACLE_SID "
                "(see .env.example)."
            )

        self.host = host
        self.port = port
        self.service_name = service_name
        self.sid = sid

        thick_env = connection.get("thick_mode_env")
        thick_requested = env_bool(thick_env, False) if thick_env else False
        client_env = connection.get("thick_mode_client_env")
        client_dir = env_optional(client_env) if client_env else None
        self.thick_mode = False
        if thick_requested:
            if not client_dir:
                raise ConfigurationError(
                    "ORACLE_THICK_MODE is enabled but no Oracle Instant Client "
                    "directory is configured (ORACLE_CLIENT_LIB_DIR)."
                )
            try:
                oracledb.init_oracle_client(lib_dir=client_dir)
            except oracledb.ProgrammingError:
                pass  # Already initialised in this process.
            self.thick_mode = True
            LOGGER.info("Oracle Thick mode enabled (lib_dir=%s)", client_dir)

    @property
    def driver_mode(self) -> str:
        return "THICK" if self.thick_mode else "THIN"

    def _connect(self):
        try:
            return oracledb.connect(user=self.user, password=self.__password, dsn=self.dsn)
        except oracledb.Error as exc:
            hint = _oracle_error_hint(exc)
            message = f"Oracle connection failed via {self.connection_mode}: {exc}"
            if hint:
                message += f" | {hint}"
            raise SourceConnectionError(message) from exc

    def test_connection(self) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                return cursor.fetchone()[0] == 1

    def describe(self) -> dict[str, Any]:
        """Session diagnostics for the `test-connection` CLI command.

        Never returns the password or a DSN containing it (DSNs built by
        oracledb.makedsn never embed credentials).
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        SYS_CONTEXT('USERENV','DB_NAME'),
                        USER,
                        SYS_CONTEXT('USERENV','CURRENT_SCHEMA'),
                        SYS_CONTEXT('USERENV','SERVICE_NAME')
                    FROM DUAL
                    """
                )
                db_name, session_user, current_schema, service_name = cursor.fetchone()
                version = connection.version
        return {
            "connection_mode": self.connection_mode,
            "driver_mode": self.driver_mode,
            "dsn": self.dsn,
            "db_name": db_name,
            "session_user": session_user,
            "current_schema": current_schema,
            "session_service_name": service_name,
            "oracle_version": version,
        }

    def query_dataframe(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.arraysize = self.arraysize
                cursor.prefetchrows = self.arraysize
                try:
                    cursor.callTimeout = self.query_timeout_seconds * 1000
                except AttributeError:
                    pass
                cursor.execute(sql, params or {})
                columns = [column[0].lower() for column in cursor.description]
                chunks: list[pd.DataFrame] = []
                while True:
                    rows = cursor.fetchmany(self.arraysize)
                    if not rows:
                        break
                    chunks.append(pd.DataFrame.from_records(rows, columns=columns))
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns)

    def inspect_table(self, owner: str, table_name: str) -> pd.DataFrame:
        sql = """
            SELECT column_id, column_name, data_type, data_length, data_precision, data_scale, nullable
            FROM all_tab_columns
            WHERE owner = :owner AND table_name = :table_name
            ORDER BY column_id
        """
        return self.query_dataframe(sql, {"owner": owner.upper(), "table_name": table_name.upper()})
