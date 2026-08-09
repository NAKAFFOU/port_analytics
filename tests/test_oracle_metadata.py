from __future__ import annotations

import pandas as pd

from src.adapters.oracle_metadata import inspect_all_views, inspect_view
from src.adapters.oracle_source_mapping import NUMERIC_COLUMNS, ORACLE_SOURCE_MAPPING


class FakeConnector:
    """Stands in for OracleConnector.query_dataframe without any real Oracle
    call, dispatching canned responses by SQL snippet — used to test the
    metadata inspector's ALL_OBJECTS/ALL_TAB_COLUMNS/ALL_VIEWS/ALL_CONSTRAINTS
    handling and its per-view failure isolation."""

    def __init__(self, fail_view: str | None = None):
        self.fail_view = fail_view

    def query_dataframe(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        params = params or {}
        table = params.get("table_name") or params.get("object_name") or params.get("view_name")

        if table == self.fail_view and "all_objects" in sql:
            raise RuntimeError("simulated ORA-00942: table or view does not exist")

        if "all_objects" in sql:
            return pd.DataFrame({"status": ["VALID"]})
        if "all_views" in sql:
            return pd.DataFrame({"view_name": [table]})
        if "all_constraints" in sql:
            return pd.DataFrame({"n": [0]})
        if "all_tab_columns" in sql:
            columns = ORACLE_SOURCE_MAPPING[table]["columns"]
            rows = [
                {
                    "column_id": i, "column_name": name,
                    "data_type": "NUMBER" if name in NUMERIC_COLUMNS else "VARCHAR2",
                    "data_length": 22, "data_precision": None, "data_scale": None,
                    "char_length": 30, "nullable": "Y",
                }
                for i, name in enumerate(columns, start=1)
            ]
            return pd.DataFrame(rows)
        if "ROWNUM = 1" in sql:
            return pd.DataFrame({"present": [1]})
        return pd.DataFrame()


def test_inspect_view_happy_path_matches_expected_columns():
    connector = FakeConnector()
    expected = set(ORACLE_SOURCE_MAPPING["RECETTE_PF"]["columns"])

    report = inspect_view(connector, "PBI_JDE", "RECETTE_PF", expected)

    assert report.accessible
    assert report.missing_columns == []
    assert report.extra_columns == []
    assert report.type_mismatches == []
    assert report.has_rows is True


def test_inspect_view_detects_missing_column():
    connector = FakeConnector()
    expected = set(ORACLE_SOURCE_MAPPING["RECETTE_PF"]["columns"]) | {"DEVISE"}

    report = inspect_view(connector, "PBI_JDE", "RECETTE_PF", expected)

    assert report.missing_columns == ["DEVISE"]


def test_inspect_view_detects_extra_column():
    connector = FakeConnector()
    expected = set(ORACLE_SOURCE_MAPPING["RECETTE_PF"]["columns"]) - {"COMPTE"}

    report = inspect_view(connector, "PBI_JDE", "RECETTE_PF", expected)

    assert report.extra_columns == ["COMPTE"]


def test_one_failing_view_does_not_block_the_others():
    connector = FakeConnector(fail_view="AINDIRECTE_COUT")

    reports = inspect_all_views(connector, "PBI_JDE")

    assert len(reports) == 5
    failed = next(r for r in reports if r.view == "AINDIRECTE_COUT")
    assert not failed.accessible
    assert failed.error is not None

    others = [r for r in reports if r.view != "AINDIRECTE_COUT"]
    assert all(r.accessible for r in others)


def test_empty_but_accessible_view_is_not_reported_as_failed():
    class EmptyRowsConnector(FakeConnector):
        def query_dataframe(self, sql, params=None):
            if "ROWNUM = 1" in sql:
                return pd.DataFrame(columns=["present"])
            return super().query_dataframe(sql, params)

    connector = EmptyRowsConnector()
    expected = set(ORACLE_SOURCE_MAPPING["RECETTE_PF"]["columns"])

    report = inspect_view(connector, "PBI_JDE", "RECETTE_PF", expected)

    assert report.accessible is True
    assert report.has_rows is False
    assert report.error is None
