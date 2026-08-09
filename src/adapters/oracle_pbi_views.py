from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.common.config import env_optional, load_yaml
from src.common.errors import ConfigurationError
from src.common.identifiers import safe_oracle_identifier
from src.connectors.factory import create_connector


class OraclePBIViewsAdapter:
    """Read-only adapter for pre-allocated analytical views in PBI_JDE.

    MONTANT is loaded exactly as returned by each view: Oracle already
    applies sign inversion, the /100 scaling and ROUND() (see
    docs/ORACLE_PBI_VIEWS.md). amount_multiplier in the profile must stay 1;
    it exists only so a future source with a different sign convention
    (e.g. SAP, Sage) can reuse this adapter without code changes.
    """

    def __init__(self, profile_path: str | Path):
        self.profile = load_yaml(profile_path)
        self.connector = create_connector(self.profile)
        self.source_system = self.profile["source_system"]
        self.oracle = self.profile.get("oracle", {})
        schema_env = self.oracle.get("schema_env", "SOURCE_DB_SCHEMA")
        default_schema = self.profile.get("schema", "PBI_JDE")
        self.schema = safe_oracle_identifier(
            env_optional(schema_env, default_schema) or default_schema,
            "schema",
        )
        currency_env = self.oracle.get(
            "default_currency_env", "SOURCE_DB_DEFAULT_CURRENCY"
        )
        self.default_currency = (
            env_optional(currency_env, "XOF") or "XOF"
        ).upper()

    def test_connection(self) -> bool:
        return self.connector.test_connection()

    def describe_connection(self) -> dict[str, Any]:
        if not hasattr(self.connector, "describe"):
            return {"connection_mode": "unknown"}
        return self.connector.describe()

    def inspect_view(self, view_name: str) -> pd.DataFrame:
        return self.connector.inspect_table(
            self.schema,
            safe_oracle_identifier(view_name, "view"),
        )

    def _identifier(self, dataset: dict[str, Any], key: str) -> str:
        return safe_oracle_identifier(dataset[key], key)

    def _query(
        self,
        dataset_name: str,
        select_items: list[tuple[str, str, bool]],
        year_from: int,
        year_to: int,
        limit: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        dataset = self.profile["datasets"][dataset_name]
        view = self._identifier(dataset, "view")
        year_column = self._identifier(dataset, "year_column")
        rendered: list[str] = []
        for config_key, alias, trim_text in select_items:
            column = self._identifier(dataset, config_key)
            expression = f"TRIM({column})" if trim_text else column
            rendered.append(f"{expression} AS {alias}")
        where = f"{year_column} BETWEEN :year_from AND :year_to"
        params: dict[str, Any] = {
            "year_from": int(year_from),
            "year_to": int(year_to),
        }
        # Filter keys must name a dataset config entry (e.g. "centre_column")
        # so the resolved Oracle column always comes from the validated
        # profile, never from caller-supplied text. Only the value is bound.
        for filter_key, value in (filters or {}).items():
            if value is None or value == "":
                continue
            if filter_key not in dataset:
                raise ConfigurationError(
                    f"Unknown filter '{filter_key}' for dataset '{dataset_name}'"
                )
            column = self._identifier(dataset, filter_key)
            bind_name = f"filter_{filter_key}"
            where += f" AND {column} = :{bind_name}"
            params[bind_name] = value
        if limit is not None:
            where += " AND ROWNUM <= :row_limit"
            params["row_limit"] = int(limit)
        sql = (
            f"SELECT {', '.join(rendered)} "
            f"FROM {self.schema}.{view} WHERE {where}"
        )
        frame = self.connector.query_dataframe(sql, params)

        if not frame.empty:
            frame["source_currency"] = self.default_currency

            if "amount_source" in frame.columns:
                multiplier = float(dataset.get("amount_multiplier", 1.0))
                frame["amount_source"] = (
                    pd.to_numeric(frame["amount_source"], errors="coerce")
                    * multiplier
                )

        return frame

    def extract_direct_allocations(
        self,
        year_from: int,
        year_to: int,
        limit: int | None = None,
        *,
        cost_centre: str | None = None,
        category: str | None = None,
        product: str | None = None,
    ) -> pd.DataFrame:
        return self._query(
            "direct_allocations",
            [
                ("year_column", "reporting_year", False),
                ("centre_column", "source_cost_centre_code", True),
                ("category_column", "service_category", True),
                ("service_column", "source_service_name", True),
                ("amount_column", "amount_source", False),
            ],
            year_from,
            year_to,
            limit,
            filters={
                "centre_column": cost_centre,
                "category_column": category,
                "service_column": product,
            },
        )

    def extract_indirect_allocations(
        self,
        year_from: int,
        year_to: int,
        limit: int | None = None,
        *,
        category: str | None = None,
        product: str | None = None,
    ) -> pd.DataFrame:
        return self._query(
            "indirect_allocations",
            [
                ("year_column", "reporting_year", False),
                ("category_column", "service_category", True),
                ("service_column", "source_service_name", True),
                ("amount_column", "amount_source", False),
            ],
            year_from,
            year_to,
            limit,
            filters={
                "category_column": category,
                "service_column": product,
            },
        )

    def extract_cost_centre_costs(
        self,
        year_from: int,
        year_to: int,
        limit: int | None = None,
        *,
        cost_centre: str | None = None,
        family: str | None = None,
        subfamily: str | None = None,
    ) -> pd.DataFrame:
        return self._query(
            "cost_centre_costs",
            [
                ("year_column", "reporting_year", False),
                ("centre_column", "source_cost_centre_code", True),
                ("centre_name_column", "source_cost_centre_name", True),
                ("family_column", "family", True),
                ("subfamily_column", "subfamily", True),
                ("amount_column", "amount_source", False),
            ],
            year_from,
            year_to,
            limit,
            filters={
                "centre_column": cost_centre,
                "family_column": family,
                "subfamily_column": subfamily,
            },
        )

    def extract_charges_reparties(
        self,
        year_from: int,
        year_to: int,
        limit: int | None = None,
        *,
        cost_centre: str | None = None,
        family: str | None = None,
        subfamily: str | None = None,
    ) -> pd.DataFrame:
        """Alternate/cross-check source for COST_CENTRE_COST. CHARGES_REPARTIES
        exposes the same distributed cost-centre costs as COUT_PAR_FCC but
        with pluralised FAMILLES/SOUS_FAMILLES columns. Not wired into
        extract_all() by default — use it to reconcile totals against
        COUT_PAR_FCC or as a substitute source if COUT_PAR_FCC becomes
        unavailable."""
        return self._query(
            "charges_reparties",
            [
                ("year_column", "reporting_year", False),
                ("centre_column", "source_cost_centre_code", True),
                ("centre_name_column", "source_cost_centre_name", True),
                ("family_column", "family", True),
                ("subfamily_column", "subfamily", True),
                ("amount_column", "amount_source", False),
            ],
            year_from,
            year_to,
            limit,
            filters={
                "centre_column": cost_centre,
                "family_column": family,
                "subfamily_column": subfamily,
            },
        )

    def extract_service_revenues(
        self,
        year_from: int,
        year_to: int,
        limit: int | None = None,
        *,
        category: str | None = None,
        product: str | None = None,
        account: str | None = None,
    ) -> pd.DataFrame:
        return self._query(
            "service_revenues",
            [
                ("year_column", "reporting_year", False),
                ("category_column", "service_category", True),
                ("service_column", "source_service_name", True),
                ("account_column", "account", True),
                ("amount_column", "amount_source", False),
            ],
            year_from,
            year_to,
            limit,
            filters={
                "category_column": category,
                "service_column": product,
                "account_column": account,
            },
        )

    def extract_all(
        self,
        year_from: int,
        year_to: int,
        limit: int | None = None,
        only_object: str | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Extract every measure, or a single Oracle view when `only_object`
        is given (matches --object on the CLI). `only_object` accepts either
        the measure name (e.g. DIRECT_ALLOCATION) or the Oracle view name
        (e.g. ADIRECTE_COUT)."""
        extractors: dict[str, tuple[str, Any]] = {
            "DIRECT_ALLOCATION": ("ADIRECTE_COUT", self.extract_direct_allocations),
            "INDIRECT_ALLOCATION": ("AINDIRECTE_COUT", self.extract_indirect_allocations),
            "COST_CENTRE_COST": ("COUT_PAR_FCC", self.extract_cost_centre_costs),
            "SERVICE_REVENUE": ("RECETTE_PF", self.extract_service_revenues),
        }
        if only_object:
            target = only_object.strip().upper()
            for measure, (view, extractor) in extractors.items():
                if target in {measure, view}:
                    return {measure: extractor(year_from, year_to, limit)}
            raise ConfigurationError(f"Unknown object for extraction: {only_object!r}")

        return {
            measure: extractor(year_from, year_to, limit)
            for measure, (_, extractor) in extractors.items()
        }
