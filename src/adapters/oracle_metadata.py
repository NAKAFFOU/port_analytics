from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.adapters.oracle_source_mapping import NUMERIC_COLUMNS, known_views
from src.common.identifiers import safe_oracle_identifier

# Deliberately restricted to ALL_OBJECTS / ALL_TAB_COLUMNS / ALL_VIEWS /
# ALL_CONSTRAINTS / ALL_CONS_COLUMNS: these are visible to any account with
# SELECT privileges on its own accessible objects. No DBA_* view is used, so
# this command works for a read-only PBI_JDE reporting account.


@dataclass
class ViewMetadataReport:
    view: str
    exists: bool
    accessible: bool
    is_view: bool | None = None
    has_rows: bool | None = None
    missing_columns: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    type_mismatches: list[str] = field(default_factory=list)
    constraint_count: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "view": self.view,
            "exists": self.exists,
            "accessible": self.accessible,
            "is_view": self.is_view,
            "has_rows": self.has_rows,
            "missing_columns": self.missing_columns,
            "extra_columns": self.extra_columns,
            "type_mismatches": self.type_mismatches,
            "constraint_count": self.constraint_count,
            "warnings": self.warnings,
            "error": self.error,
        }


def _object_status(connector, schema: str, view: str) -> tuple[bool, str | None]:
    frame = connector.query_dataframe(
        """
        SELECT status FROM all_objects
        WHERE owner = :owner AND object_name = :object_name
          AND object_type IN ('VIEW', 'TABLE')
        """,
        {"owner": schema, "object_name": view},
    )
    if frame.empty:
        return False, None
    return True, str(frame.iloc[0]["status"])


def _columns(connector, schema: str, view: str) -> pd.DataFrame:
    return connector.query_dataframe(
        """
        SELECT column_id, column_name, data_type, data_length, data_precision,
               data_scale, char_length, nullable
        FROM all_tab_columns
        WHERE owner = :owner AND table_name = :table_name
        ORDER BY column_id
        """,
        {"owner": schema, "table_name": view},
    )


def _is_view(connector, schema: str, view: str) -> bool:
    frame = connector.query_dataframe(
        "SELECT view_name FROM all_views WHERE owner = :owner AND view_name = :view_name",
        {"owner": schema, "view_name": view},
    )
    return not frame.empty


def _constraint_count(connector, schema: str, view: str) -> int:
    frame = connector.query_dataframe(
        """
        SELECT COUNT(*) AS n
        FROM all_constraints c
        JOIN all_cons_columns cc
          ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name
        WHERE c.owner = :owner AND c.table_name = :table_name
        """,
        {"owner": schema, "table_name": view},
    )
    return int(frame.iloc[0]["n"]) if not frame.empty else 0


def _has_rows(connector, schema: str, view: str) -> bool:
    safe_schema = safe_oracle_identifier(schema, "schema")
    safe_view = safe_oracle_identifier(view, "view")
    frame = connector.query_dataframe(
        f"SELECT 1 AS present FROM {safe_schema}.{safe_view} WHERE ROWNUM = 1"
    )
    return not frame.empty


def inspect_view(connector, schema: str, view: str, expected_columns: set[str]) -> ViewMetadataReport:
    """Inspect a single view. Any failure is captured on the report rather
    than raised, so one broken view never blocks the others (see
    inspect_all_views)."""
    try:
        exists, status = _object_status(connector, schema, view)
    except Exception as exc:  # noqa: BLE001
        return ViewMetadataReport(view, exists=False, accessible=False, error=str(exc))

    if not exists:
        return ViewMetadataReport(
            view, exists=False, accessible=False,
            error=f"{schema}.{view} not found in ALL_OBJECTS",
        )
    if status and status != "VALID":
        return ViewMetadataReport(
            view, exists=True, accessible=False,
            error=f"{schema}.{view} exists but status is {status}",
        )

    report = ViewMetadataReport(view, exists=True, accessible=True)

    try:
        report.is_view = _is_view(connector, schema, view)
        if not report.is_view:
            report.warnings.append(f"{schema}.{view} is not registered in ALL_VIEWS (table or synonym?)")
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"ALL_VIEWS lookup failed: {exc}")

    try:
        report.constraint_count = _constraint_count(connector, schema, view)
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"ALL_CONSTRAINTS/ALL_CONS_COLUMNS lookup failed: {exc}")

    try:
        columns_frame = _columns(connector, schema, view)
    except Exception as exc:  # noqa: BLE001
        report.accessible = False
        report.error = f"ALL_TAB_COLUMNS lookup failed: {exc}"
        return report

    if columns_frame.empty:
        report.accessible = False
        report.error = f"No columns visible for {schema}.{view} (missing grants?)"
        return report

    real_columns = {str(name).upper() for name in columns_frame["column_name"]}
    report.missing_columns = sorted(expected_columns - real_columns)
    report.extra_columns = sorted(real_columns - expected_columns)

    for _, row in columns_frame.iterrows():
        name = str(row["column_name"]).upper()
        if name not in expected_columns:
            continue
        data_type = str(row["data_type"]).upper()
        is_numeric_type = "NUMBER" in data_type or "FLOAT" in data_type
        if name in NUMERIC_COLUMNS and not is_numeric_type:
            report.type_mismatches.append(f"{name}: expected NUMBER-like, found {data_type}")
        if name not in NUMERIC_COLUMNS and is_numeric_type:
            report.type_mismatches.append(f"{name}: expected CHAR/VARCHAR2-like, found {data_type}")

    try:
        report.has_rows = _has_rows(connector, schema, view)
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"Row-presence probe failed: {exc}")

    return report


def inspect_all_views(connector, schema: str) -> list[ViewMetadataReport]:
    from src.adapters.oracle_source_mapping import ORACLE_SOURCE_MAPPING

    reports = []
    for view in known_views():
        expected = set(ORACLE_SOURCE_MAPPING[view]["columns"])
        reports.append(inspect_view(connector, schema, view, expected))
    return reports


def write_report(reports: list[ViewMetadataReport], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def print_report(reports: list[ViewMetadataReport]) -> None:
    for r in reports:
        state = "OK" if (r.accessible and not r.error) else "FAILED"
        print(f"[{state}] {r.view} (exists={r.exists}, accessible={r.accessible}, has_rows={r.has_rows})")
        if r.error:
            print(f"    error: {r.error}")
        if r.missing_columns:
            print(f"    missing columns: {r.missing_columns}")
        if r.extra_columns:
            print(f"    extra columns: {r.extra_columns}")
        if r.type_mismatches:
            print(f"    type mismatches: {r.type_mismatches}")
        for warning in r.warnings:
            print(f"    warning: {warning}")
