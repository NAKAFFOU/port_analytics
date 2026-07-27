from __future__ import annotations

import hashlib
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from src.common.config import base_currency, env_bool, get_settings, load_yaml, project_path
from src.currency.converter import CurrencyConverter
from src.currency.repository import FxRate, FxRateRepository
from src.db.schema import connect, create_schema
from src.db.seed_demo import ACTIONS, ALERT_THRESHOLDS, KPI_DEFINITIONS
from src.pipeline.kpi_formulas import analytical_margin_pct, cost_recovery_ratio
from src.rules.alerts import generate_alerts

MEASURE_CONFIG = {
    "DIRECT_ALLOCATION": {
        "source_view": "ADIRECTE_COUT",
        "required": ["reporting_year", "source_cost_centre_code", "source_service_name", "amount_source"],
        "group": ["reporting_year", "source_cost_centre_code", "service_category", "source_service_name", "source_currency"],
        "force_absolute": True,
    },
    "INDIRECT_ALLOCATION": {
        "source_view": "AINDIRECTE_COUT",
        "required": ["reporting_year", "source_service_name", "amount_source"],
        "group": ["reporting_year", "service_category", "source_service_name", "source_currency"],
        "force_absolute": True,
    },
    "COST_CENTRE_COST": {
        "source_view": "COUT_PAR_FCC",
        "required": ["reporting_year", "source_cost_centre_code", "amount_source"],
        "group": [
            "reporting_year", "source_cost_centre_code", "source_cost_centre_name",
            "family", "subfamily", "source_currency",
        ],
        "force_absolute": True,
    },
    "SERVICE_REVENUE": {
        "source_view": "RECETTE_PF",
        "required": ["reporting_year", "source_service_name", "amount_source"],
        "group": [
            "reporting_year", "service_category", "source_service_name",
            "account", "source_currency",
        ],
        # Revenue keeps its natural sign — RECETTE_PF.MONTANT is already
        # positive; forcing abs() here would silently hide a genuine
        # negative-revenue source row (credit note, correction) instead of
        # surfacing it as a data-quality signal.
        "force_absolute": False,
    },
}


@dataclass(frozen=True)
class OracleViewsRunResult:
    batch_id: str
    facts_loaded: int
    facts_rejected: int
    occ_rows: int
    psl_rows: int
    alerts: int


def _text(value: object, default: str = "") -> str:
    if value is None or pd.isna(value):
        return default
    text = str(value)
    if env_bool("TRIM_ORACLE_TEXT", True):
        # JDE CHAR/NCHAR columns are fixed-width and space-padded.
        text = text.strip()
    return text


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def safe_year(value: object) -> int | None:
    """Robust ANNEE conversion: None / "" / "   " -> None; "2026", 2026,
    2026.0 or Decimal("2026") -> 2026; anything non-convertible -> None
    (surfaced as a missing-required-column validation issue upstream, never
    a raw `int(value)` crash on an empty string)."""
    if _is_blank(value):
        return None
    text = value.strip() if isinstance(value, str) else value
    try:
        return int(Decimal(str(text)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def safe_amount(value: object) -> float | None:
    """Robust MONTANT conversion. Oracle already applies sign inversion,
    /100 scaling and ROUND() inside the PBI_JDE views (see
    docs/ORACLE_PBI_VIEWS.md); this function only parses the value — it
    never rescales or flips the sign."""
    if _is_blank(value):
        return None
    text = value.strip() if isinstance(value, str) else value
    try:
        return float(Decimal(str(text)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _slug(value: str, max_length: int = 26) -> str:
    normalised = unicodedata.normalize("NFKD", value)
    ascii_value = normalised.encode("ascii", "ignore").decode("ascii")
    token = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value.upper()).strip("-")
    token = token or "UNMAPPED"
    if len(token) <= max_length:
        return token
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:6].upper()
    return f"{token[:max_length-7]}-{digest}"


def _period_id(year: int) -> str:
    return f"{int(year)}-ANNUAL"


def _load_optional_mapping(path_value: str | None) -> pd.DataFrame:
    if not path_value:
        return pd.DataFrame()
    path = project_path(path_value)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    frame = pd.read_csv(path, dtype=str).fillna("")
    return frame


class SemanticMapper:
    """Maps raw JDE source labels to stable internal codes and canonical
    display names. Also carries the optional French/English display-label
    translation for centres, services/categories, families, sub-families
    and accounts (see config/mappings/oracle_pbi_views/*.csv) — these are
    display-only: they never change amounts, and unmapped values fall back
    to the raw source text in both languages."""

    def __init__(self, profile: dict):
        mapping = profile.get("mappings", {})
        self.centres = _load_optional_mapping(mapping.get("cost_centres"))
        self.services = _load_optional_mapping(mapping.get("service_lines"))
        self.families = _load_optional_mapping(mapping.get("families"))
        self.subfamilies = _load_optional_mapping(mapping.get("subfamilies"))
        self.accounts = _load_optional_mapping(mapping.get("accounts"))

        self.centre_lookup: dict[str, dict[str, str]] = {}
        for _, row in self.centres.iterrows():
            key = _text(row.get("source_code")).upper()
            if key:
                self.centre_lookup[key] = {
                    "target_code": _text(row.get("target_code")),
                    "target_name": _text(row.get("target_name")),
                    "target_name_en": _text(row.get("target_name_en")),
                }

        self.service_lookup: dict[tuple[str, str], dict[str, str]] = {}
        for _, row in self.services.iterrows():
            key = (
                _text(row.get("source_category")).upper(),
                _text(row.get("source_product")).upper(),
            )
            if key[1]:
                self.service_lookup[key] = {
                    "target_service_code": _text(row.get("target_service_code")),
                    "target_service_name": _text(row.get("target_service_name")),
                    "target_category_name": _text(row.get("target_category_name")),
                    "target_service_name_en": _text(row.get("target_service_name_en")),
                    "target_category_name_en": _text(row.get("target_category_name_en")),
                }

        self.family_lookup = self._label_lookup(self.families, "source_family")
        self.subfamily_lookup = self._label_lookup(self.subfamilies, "source_subfamily")
        self.account_lookup = self._label_lookup(self.accounts, "source_account")

    @staticmethod
    def _label_lookup(frame: pd.DataFrame, key_column: str) -> dict[str, tuple[str, str]]:
        lookup: dict[str, tuple[str, str]] = {}
        for _, row in frame.iterrows():
            source_value = _text(row.get(key_column))
            key = source_value.upper()
            if key:
                lookup[key] = (
                    _text(row.get("label_fr")) or source_value,
                    _text(row.get("label_en")) or source_value,
                )
        return lookup

    def centre(self, source_code: str, source_name: str | None = None) -> tuple[str, str, str]:
        """Returns (internal_code, name_fr, name_en)."""
        source_code = _text(source_code)
        source_name = _text(source_name, source_code)
        mapped = self.centre_lookup.get(source_code.upper())
        if mapped:
            code = mapped["target_code"] or f"OCC-{_slug(source_code)}"
            name = mapped["target_name"] or source_name
            name_en = mapped["target_name_en"] or name
            return code, name, name_en
        return f"OCC-{_slug(source_code)}", source_name, source_name

    def service(self, category: str | None, product: str) -> tuple[str, str, str, str, str]:
        """Returns (internal_code, name_fr, category_fr, name_en, category_en)."""
        category = _text(category, "Uncategorised")
        product = _text(product)
        mapped = self.service_lookup.get((category.upper(), product.upper()))
        if mapped:
            code = mapped["target_service_code"] or f"PSL-{_slug(category + '-' + product)}"
            name = mapped["target_service_name"] or product
            target_category = mapped["target_category_name"] or category
            name_en = mapped["target_service_name_en"] or name
            category_en = mapped["target_category_name_en"] or target_category
            return code, name, target_category, name_en, category_en
        return (
            f"PSL-{_slug(category + '-' + product)}", product, category, product, category,
        )

    def family_label(self, value: str | None) -> tuple[str | None, str | None]:
        return self._label(self.family_lookup, value)

    def subfamily_label(self, value: str | None) -> tuple[str | None, str | None]:
        return self._label(self.subfamily_lookup, value)

    def account_label(self, value: str | None) -> tuple[str | None, str | None]:
        return self._label(self.account_lookup, value)

    @staticmethod
    def _label(lookup: dict[str, tuple[str, str]], value: str | None) -> tuple[str | None, str | None]:
        text = _text(value)
        if not text:
            return None, None
        mapped = lookup.get(text.upper())
        if mapped:
            return mapped
        return text, text


def _seed_reference_data(conn) -> None:
    conn.executemany(
        """INSERT INTO alert_thresholds(rule_name,indicator,threshold_val,severity,description)
        VALUES(?,?,?,?,?)
        ON CONFLICT(rule_name) DO UPDATE SET
          indicator=excluded.indicator,
          threshold_val=excluded.threshold_val,
          severity=excluded.severity,
          description=excluded.description""",
        ALERT_THRESHOLDS,
    )
    conn.executemany(
        """INSERT INTO decision_support_actions
        (rule_name,recommended_action,escalation_path,priority_class,response_timeframe)
        VALUES(?,?,?,?,?)
        ON CONFLICT(rule_name) DO UPDATE SET
          recommended_action=excluded.recommended_action,
          escalation_path=excluded.escalation_path,
          priority_class=excluded.priority_class,
          response_timeframe=excluded.response_timeframe""",
        ACTIONS,
    )
    conn.executemany(
        """INSERT INTO kpi_definitions
        (kpi_code,kpi_name,formula,interpretation,management_use,default_threshold,related_alert)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(kpi_code) DO UPDATE SET
          kpi_name=excluded.kpi_name,
          formula=excluded.formula,
          interpretation=excluded.interpretation,
          management_use=excluded.management_use,
          default_threshold=excluded.default_threshold,
          related_alert=excluded.related_alert""",
        KPI_DEFINITIONS,
    )


def reset_for_oracle_views() -> None:
    """Replace the analytical dataset while preserving approved FX rates."""
    tables = [
        "decision_alerts", "psl_indicators", "occ_indicators",
        "allocation_results_phase2", "allocation_results_phase1",
        "oracle_view_facts", "activity_volumes", "service_budgets",
        "revenue_transactions", "actual_transactions", "budgets",
        "allocation_rules_phase2", "allocation_rules_phase1",
        "data_quality_issues", "data_load_runs", "ingestion_batches",
        "reporting_periods", "service_lines", "account_categories",
        "cost_centres", "decision_support_actions", "kpi_definitions",
        "alert_thresholds",
    ]
    with connect() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        for table in tables:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("PRAGMA foreign_keys=ON")
        _seed_reference_data(conn)


def _normalise_frame(
    frame: pd.DataFrame, measure_type: str
) -> tuple[pd.DataFrame, list[str], int]:
    """Returns (grouped_frame, issues, valid_row_count). valid_row_count is
    the row count *before* the dimensional groupby, for traceability
    (data_load_runs.rows_valid) — the returned grouped_frame row count is
    the number of distinct dimension combinations, not raw valid rows."""
    config = MEASURE_CONFIG[measure_type]
    work = frame.copy()
    issues: list[str] = []

    for column in [
        "source_cost_centre_code", "source_cost_centre_name",
        "service_category", "source_service_name", "source_currency",
        "account", "family", "subfamily",
    ]:
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_text)

    if "reporting_year" not in work.columns:
        work["reporting_year"] = pd.NA
    work["reporting_year"] = work["reporting_year"].map(safe_year)
    if "amount_source" not in work.columns:
        work["amount_source"] = pd.NA
    work["amount_source"] = work["amount_source"].map(safe_amount)

    invalid = pd.Series(False, index=work.index)
    for column in config["required"]:
        if column in {"reporting_year", "amount_source"}:
            mask = work[column].isna()
        else:
            mask = work[column].astype(str).str.strip().eq("")
        if mask.any():
            issues.append(f"{measure_type}: {int(mask.sum())} rows missing {column}")
            invalid |= mask

    work = work.loc[~invalid].copy()
    valid_row_count = len(work)
    if work.empty:
        return work, issues, valid_row_count

    work["reporting_year"] = work["reporting_year"].astype(int)
    work["service_category"] = work["service_category"].replace("", "Uncategorised")
    work["source_currency"] = work["source_currency"].str.upper()
    if config.get("force_absolute"):
        # Costs are always displayed as a positive magnitude — applied per
        # row, before aggregation, so a group can't cancel itself out.
        # Revenue (SERVICE_REVENUE) is exempt: RECETTE_PF.MONTANT is
        # already positive, and a genuine negative row there is a
        # data-quality signal, not something to hide.
        work["amount_source"] = work["amount_source"].abs()
    grouped = work.groupby(config["group"], dropna=False, as_index=False)["amount_source"].sum()
    return grouped, issues, valid_row_count


def _insert_issue(conn, batch_id: str, description: str, severity: str = "WARNING") -> None:
    conn.execute(
        """INSERT INTO data_quality_issues
        (batch_id,source_system,issue_type,severity,description)
        VALUES(?,?,?,?,?)""",
        (batch_id, "ORACLE_PBI_VIEWS", "SOURCE_VALIDATION", severity, description),
    )


def _upsert_period(conn, year: int) -> str:
    pid = _period_id(year)
    conn.execute(
        """INSERT INTO reporting_periods
        (period_id,year,month,period_granularity,period_label,period_end_date,is_closed)
        VALUES(?,?,NULL,'YEAR',?,?,1)
        ON CONFLICT(period_id) DO NOTHING""",
        (pid, year, f"Annual {year}", date(year, 12, 31).isoformat()),
    )
    return pid


def _upsert_centre(conn, code: str, name: str, name_en: str | None = None, pool: bool = False) -> None:
    conn.execute(
        """INSERT INTO cost_centres(centre_code,centre_name,centre_name_en,tier,centre_type,parent_code)
        VALUES(?,?,?,?,?,NULL)
        ON CONFLICT(centre_code) DO UPDATE SET
          centre_name=excluded.centre_name,
          centre_name_en=excluded.centre_name_en""",
        (code, name, name_en or name, "POOL" if pool else "OCC", "POOL" if pool else "OPERATIONAL"),
    )


def _upsert_service(
    conn, code: str, name: str, category: str,
    name_en: str | None = None, category_en: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO service_lines
        (service_code,service_name,service_name_en,service_category,service_category_en,
         revenue_type,primary_driver)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(service_code) DO UPDATE SET
          service_name=excluded.service_name,
          service_name_en=excluded.service_name_en,
          service_category=excluded.service_category,
          service_category_en=excluded.service_category_en""",
        (
            code, name, name_en or name, category, category_en or category,
            "Source analytical view", "Pre-allocated in Oracle",
        ),
    )


def ingest_frames(
    frames: dict[str, pd.DataFrame],
    profile: dict,
    year_from: int,
    year_to: int,
    source_schema: str,
    replace: bool = True,
    filters_used: dict | None = None,
) -> OracleViewsRunResult:
    create_schema()
    if replace:
        reset_for_oracle_views()

    run_started = time.monotonic()
    batch_id = f"PBI-{uuid.uuid4().hex[:12].upper()}"
    started = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """INSERT INTO ingestion_batches
            (batch_id,source_system,date_from,date_to,started_at,status)
            VALUES(?,?,?,?,?,'STARTED')""",
            (
                batch_id,
                "ORACLE_PBI_VIEWS",
                f"{year_from}-01-01",
                f"{year_to}-12-31",
                started,
            ),
        )

    mapper = SemanticMapper(profile)
    converter = CurrencyConverter()
    fx_policy = profile.get("oracle", {}).get("annual_fx_policy", "ANNUAL_AVERAGE")
    facts_loaded = 0
    facts_rejected = 0
    facts_loaded_by_measure: dict[str, int] = {}
    facts_rejected_by_measure: dict[str, int] = {}
    raw_row_counts: dict[str, int] = {
        measure: len(frames.get(measure, pd.DataFrame())) for measure in MEASURE_CONFIG
    }
    valid_row_counts: dict[str, int] = {}

    # Cost-centre descriptions improve direct-allocation labels.
    centre_names: dict[str, str] = {}
    cost_frame, cost_issues, cost_valid_rows = _normalise_frame(
        frames.get("COST_CENTRE_COST", pd.DataFrame()), "COST_CENTRE_COST"
    )
    valid_row_counts["COST_CENTRE_COST"] = cost_valid_rows
    for _, row in cost_frame.iterrows():
        centre_names[_text(row["source_cost_centre_code"]).upper()] = _text(
            row["source_cost_centre_name"], _text(row["source_cost_centre_code"])
        )
    normalised_frames: dict[str, pd.DataFrame] = {"COST_CENTRE_COST": cost_frame}
    issues = list(cost_issues)
    for measure_type in ["DIRECT_ALLOCATION", "INDIRECT_ALLOCATION", "SERVICE_REVENUE"]:
        normalised, found_issues, valid_rows = _normalise_frame(
            frames.get(measure_type, pd.DataFrame()), measure_type
        )
        normalised_frames[measure_type] = normalised
        valid_row_counts[measure_type] = valid_rows
        issues.extend(found_issues)

    # Validate all required annual FX rates before loading any analytical fact.
    fx_pairs: set[tuple[int, str]] = set()
    for frame in normalised_frames.values():
        if frame.empty:
            continue
        for _, fx_row in frame[["reporting_year", "source_currency"]].drop_duplicates().iterrows():
            fx_pairs.add((int(fx_row["reporting_year"]), _text(fx_row["source_currency"], "XOF").upper()))
    try:
        for year, currency in sorted(fx_pairs):
            converter.convert_annual_flow(
                1.0, currency, base_currency(), year, policy=fx_policy
            )
    except Exception as exc:
        with connect() as conn:
            _insert_issue(conn, batch_id, f"FX validation failed: {exc}", "ERROR")
            conn.execute(
                """UPDATE ingestion_batches SET completed_at=?,status='FAILED',
                error_message=? WHERE batch_id=?""",
                (datetime.now().isoformat(timespec="seconds"), str(exc), batch_id),
            )
        raise

    with connect() as conn:
        for issue in issues:
            _insert_issue(conn, batch_id, issue)

        _upsert_centre(conn, "POOL-INDIRECT", "Indirect Cost Pool", pool=True)

        for measure_type, frame in normalised_frames.items():
            config = MEASURE_CONFIG[measure_type]
            for _, row in frame.iterrows():
                try:
                    year = int(row["reporting_year"])
                    period_id = _upsert_period(conn, year)
                    source_currency = _text(row.get("source_currency"), "XOF").upper()
                    conversion = converter.convert_annual_flow(
                        float(row["amount_source"]),
                        source_currency,
                        base_currency(),
                        year,
                        policy=fx_policy,
                    )

                    source_centre = _text(row.get("source_cost_centre_code"))
                    source_centre_name = _text(
                        row.get("source_cost_centre_name"),
                        centre_names.get(source_centre.upper(), source_centre),
                    )
                    centre_code = None
                    if source_centre:
                        centre_code, centre_name, _centre_name_en = mapper.centre(
                            source_centre, source_centre_name
                        )
                        _upsert_centre(conn, centre_code, centre_name, _centre_name_en)

                    category = _text(row.get("service_category"), "Uncategorised")
                    category_en = category
                    source_service = _text(row.get("source_service_name"))
                    service_code = None
                    if source_service:
                        service_code, service_name, target_category, service_name_en, target_category_en = (
                            mapper.service(category, source_service)
                        )
                        category = target_category
                        category_en = target_category_en
                        _upsert_service(conn, service_code, service_name, category, service_name_en, category_en)

                    # account (RECETTE_PF.COMPTE) and family/subfamily
                    # (COUT_PAR_FCC/CHARGES_REPARTIES) are additional
                    # dimensions present only for some measures — captured
                    # as-is, never used to recompute an amount. The _en
                    # variants are display-only translations (see
                    # config/mappings/oracle_pbi_views/*.csv); unmapped
                    # values fall back to the raw source text.
                    account = _text(row.get("account")) or None
                    family = _text(row.get("family")) or None
                    subfamily = _text(row.get("subfamily")) or None
                    _, account_en = mapper.account_label(account)
                    _, family_en = mapper.family_label(family)
                    _, subfamily_en = mapper.subfamily_label(subfamily)

                    hash_fields = [
                        measure_type, str(year), source_centre,
                        category, source_service, f"{float(row['amount_source']):.8f}",
                        account or "", family or "", subfamily or "",
                    ]
                    source_hash = hashlib.sha256(
                        "|".join(hash_fields).encode("utf-8")
                    ).hexdigest()
                    conn.execute(
                        """INSERT INTO oracle_view_facts
                        (batch_id,source_system,source_schema,source_view,measure_type,
                         reporting_year,period_id,source_cost_centre_code,
                         source_cost_centre_name,centre_code,service_category,service_category_en,
                         source_service_name,service_code,account,account_en,family,family_en,
                         subfamily,subfamily_en,
                         amount_source,source_currency,
                         fx_rate_to_base,fx_rate_date,fx_provider,amount_base,
                         base_currency,source_row_hash)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            batch_id, "ORACLE_PBI_VIEWS", source_schema,
                            config["source_view"], measure_type, year, period_id,
                            source_centre or None, source_centre_name or None,
                            centre_code, category or None, category_en or None,
                            source_service or None,
                            service_code, account, account_en, family, family_en,
                            subfamily, subfamily_en,
                            float(row["amount_source"]), source_currency,
                            conversion.rate, conversion.rate_date.isoformat(),
                            conversion.provider, conversion.amount, base_currency(),
                            source_hash,
                        ),
                    )
                    facts_loaded += 1
                    facts_loaded_by_measure[measure_type] = (
                        facts_loaded_by_measure.get(measure_type, 0) + 1
                    )
                except Exception as exc:
                    facts_rejected += 1
                    facts_rejected_by_measure[measure_type] = (
                        facts_rejected_by_measure.get(measure_type, 0) + 1
                    )
                    _insert_issue(conn, batch_id, f"{measure_type}: {exc}", "ERROR")

        conn.execute(
            """UPDATE ingestion_batches SET completed_at=?,rows_extracted=?,
            rows_loaded=?,rows_rejected=?,status='COMPLETED' WHERE batch_id=?""",
            (
                datetime.now().isoformat(timespec="seconds"),
                facts_loaded + facts_rejected,
                facts_loaded,
                facts_rejected,
                batch_id,
            ),
        )

        duration_seconds = round(time.monotonic() - run_started, 3)
        run_filters = dict(filters_used or {})
        run_filters.setdefault("year_from", year_from)
        run_filters.setdefault("year_to", year_to)
        for measure_type, config in MEASURE_CONFIG.items():
            if measure_type not in frames:
                continue  # Not requested in this run (e.g. --object filter).
            extracted = raw_row_counts.get(measure_type, 0)
            valid = valid_row_counts.get(measure_type, 0)
            loaded = facts_loaded_by_measure.get(measure_type, 0)
            rejected = (extracted - valid) + facts_rejected_by_measure.get(measure_type, 0)
            # An empty-but-accessible view is a successful run with zero
            # rows, not a failure (see docs: "accessible but no data").
            status = "SUCCESS" if rejected == 0 else "PARTIAL_SUCCESS"
            conn.execute(
                """INSERT INTO data_load_runs
                (load_id,source_system,source_schema,source_object,started_at,
                 completed_at,status,rows_extracted,rows_valid,rows_loaded,
                 rows_rejected,filters_used,error_message)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (
                    f"{batch_id}-{measure_type}",
                    "ORACLE_PBI_VIEWS",
                    source_schema,
                    config["source_view"],
                    started,
                    datetime.now().isoformat(timespec="seconds"),
                    status,
                    extracted,
                    valid,
                    loaded,
                    rejected,
                    str({**run_filters, "duration_seconds": duration_seconds}),
                ),
            )

    occ_rows, psl_rows = build_analytics_from_preallocated_views()
    alert_count = generate_alerts()
    return OracleViewsRunResult(
        batch_id, facts_loaded, facts_rejected, occ_rows, psl_rows, alert_count
    )


def build_analytics_from_preallocated_views() -> tuple[int, int]:
    with connect() as conn:
        facts = pd.read_sql_query("SELECT * FROM oracle_view_facts", conn)
        conn.execute("DELETE FROM decision_alerts")
        conn.execute("DELETE FROM occ_indicators")
        conn.execute("DELETE FROM psl_indicators")
        conn.execute("DELETE FROM allocation_results_phase1")
        conn.execute("DELETE FROM allocation_results_phase2")

        costs = facts[facts["measure_type"] == "COST_CENTRE_COST"]
        if not costs.empty:
            occ = costs.groupby(
                ["centre_code", "period_id"], as_index=False
            )["amount_base"].sum()
            occ["total_direct_cost"] = occ["amount_base"]
            occ["allocated_ssc_cost"] = 0.0
            occ["total_occ_cost"] = occ["amount_base"]
            occ["budget_direct"] = pd.NA
            occ["cost_variance_abs"] = pd.NA
            occ["cost_variance_pct"] = pd.NA
            occ["overhead_share_pct"] = pd.NA
            occ["budget_consumption_ytd"] = pd.NA
            occ["top_cost_category_share"] = pd.NA
            occ["currency_code"] = base_currency()
            occ[
                [
                    "centre_code", "period_id", "total_direct_cost",
                    "allocated_ssc_cost", "total_occ_cost", "budget_direct",
                    "cost_variance_abs", "cost_variance_pct",
                    "overhead_share_pct", "budget_consumption_ytd",
                    "top_cost_category_share", "currency_code",
                ]
            ].to_sql("occ_indicators", conn, if_exists="append", index=False)
            occ_rows = len(occ)
        else:
            occ_rows = 0

        direct = facts[facts["measure_type"] == "DIRECT_ALLOCATION"]
        indirect = facts[facts["measure_type"] == "INDIRECT_ALLOCATION"]
        revenues = facts[facts["measure_type"] == "SERVICE_REVENUE"]

        if not direct.empty:
            direct_detail = direct.groupby(
                ["centre_code", "service_code", "period_id"], as_index=False
            )["amount_base"].sum()
            direct_detail["driver_code"] = "PREALLOCATED_VIEW"
            direct_detail["allocation_pct"] = 100.0
            direct_detail["direct_allocated_cost"] = direct_detail["amount_base"]
            direct_detail["indirect_allocated_cost"] = 0.0
            direct_detail["total_allocated_cost"] = direct_detail["amount_base"]
            direct_detail["currency_code"] = base_currency()
            direct_detail.rename(
                columns={"centre_code": "source_occ", "service_code": "destination_psl"},
                inplace=True,
            )
            direct_detail[
                [
                    "source_occ", "destination_psl", "period_id", "driver_code",
                    "allocation_pct", "direct_allocated_cost",
                    "indirect_allocated_cost", "total_allocated_cost", "currency_code",
                ]
            ].to_sql("allocation_results_phase2", conn, if_exists="append", index=False)

        if not indirect.empty:
            indirect_detail = indirect.groupby(
                ["service_code", "period_id"], as_index=False
            )["amount_base"].sum()
            indirect_detail["source_occ"] = "POOL-INDIRECT"
            indirect_detail["driver_code"] = "PREALLOCATED_VIEW"
            indirect_detail["allocation_pct"] = 100.0
            indirect_detail["direct_allocated_cost"] = 0.0
            indirect_detail["indirect_allocated_cost"] = indirect_detail["amount_base"]
            indirect_detail["total_allocated_cost"] = indirect_detail["amount_base"]
            indirect_detail["currency_code"] = base_currency()
            indirect_detail.rename(columns={"service_code": "destination_psl"}, inplace=True)
            indirect_detail[
                [
                    "source_occ", "destination_psl", "period_id", "driver_code",
                    "allocation_pct", "direct_allocated_cost",
                    "indirect_allocated_cost", "total_allocated_cost", "currency_code",
                ]
            ].to_sql("allocation_results_phase2", conn, if_exists="append", index=False)

        keys = pd.concat(
            [
                frame[["service_code", "period_id"]]
                for frame in [direct, indirect, revenues]
                if not frame.empty
            ],
            ignore_index=True,
        ).drop_duplicates()

        if keys.empty:
            return occ_rows, 0

        def grouped(frame: pd.DataFrame, name: str) -> pd.DataFrame:
            if frame.empty:
                return pd.DataFrame(columns=["service_code", "period_id", name])
            return frame.groupby(
                ["service_code", "period_id"], as_index=False
            )["amount_base"].sum().rename(columns={"amount_base": name})

        psl = keys.merge(grouped(direct, "direct_allocated_cost"), on=["service_code", "period_id"], how="left")
        psl = psl.merge(grouped(indirect, "indirect_allocated_cost"), on=["service_code", "period_id"], how="left")
        psl = psl.merge(grouped(revenues, "actual_revenue"), on=["service_code", "period_id"], how="left")
        psl[["direct_allocated_cost", "indirect_allocated_cost", "actual_revenue"]] = psl[
            ["direct_allocated_cost", "indirect_allocated_cost", "actual_revenue"]
        ].fillna(0.0)
        psl["total_attributed_cost"] = psl["direct_allocated_cost"] + psl["indirect_allocated_cost"]
        psl["budgeted_revenue"] = pd.NA
        psl["activity_volume"] = pd.NA
        psl["service_net_position"] = psl["actual_revenue"] - psl["total_attributed_cost"]
        psl["analytical_margin_pct"] = analytical_margin_pct(
            psl["service_net_position"], psl["actual_revenue"]
        )
        psl["cost_recovery_ratio"] = cost_recovery_ratio(
            psl["actual_revenue"], psl["total_attributed_cost"]
        )
        psl["revenue_variance_pct"] = pd.NA
        psl["cost_efficiency_index"] = pd.NA
        psl["revenue_budget_achievement_ytd"] = pd.NA
        psl["currency_code"] = base_currency()
        psl[
            [
                "service_code", "period_id", "direct_allocated_cost",
                "indirect_allocated_cost", "total_attributed_cost", "actual_revenue",
                "budgeted_revenue", "activity_volume", "service_net_position",
                "analytical_margin_pct", "cost_recovery_ratio",
                "revenue_variance_pct", "cost_efficiency_index",
                "revenue_budget_achievement_ytd", "currency_code",
            ]
        ].to_sql("psl_indicators", conn, if_exists="append", index=False)
        return occ_rows, len(psl)


def run_oracle_views_ingestion(
    year_from: int,
    year_to: int,
    profile_path: str | None = None,
    replace: bool = True,
    limit: int | None = None,
    only_object: str | None = None,
) -> OracleViewsRunResult:
    settings = get_settings()
    profile_path = profile_path or settings["source"]["active_profile"]
    profile = load_yaml(profile_path)
    from src.adapters.oracle_pbi_views import OraclePBIViewsAdapter
    adapter = OraclePBIViewsAdapter(profile_path)
    frames = adapter.extract_all(year_from, year_to, limit=limit, only_object=only_object)
    return ingest_frames(
        frames,
        profile,
        year_from,
        year_to,
        adapter.schema,
        replace=replace,
        filters_used={"limit": limit, "object": only_object},
    )


def load_csv_frames(
    sample_dir: str | Path,
    filenames: dict[str, str] | None = None,
    encoding: str = "utf-8",
) -> dict[str, pd.DataFrame]:
    directory = project_path(sample_dir)
    files = filenames or {
        "DIRECT_ALLOCATION": "adirecte_cout.csv",
        "INDIRECT_ALLOCATION": "aindirecte_cout.csv",
        "COST_CENTRE_COST": "cout_par_fcc.csv",
        "SERVICE_REVENUE": "recette_pf.csv",
    }
    rename = {
        "ANNEE": "reporting_year",
        "CODE_CC": "source_cost_centre_code",
        "DESC_CC": "source_cost_centre_name",
        "CATEGORIE": "service_category",
        "PRODUIT_FINI": "source_service_name",
        "MONTANT": "amount_source",
        "DEVISE": "source_currency",
        "COMPTE": "account",
        # COUT_PAR_FCC uses the singular form, CHARGES_REPARTIES the plural
        # — both are harmonised to the same internal fields here.
        "FAMILLE": "family",
        "SOUS_FAMILLE": "subfamily",
        "FAMILLES": "family",
        "SOUS_FAMILLES": "subfamily",
    }
    result: dict[str, pd.DataFrame] = {}
    for measure, filename in files.items():
        frame = pd.read_csv(directory / filename, dtype=str, encoding=encoding)
        frame.rename(columns=rename, inplace=True)
        if "source_currency" not in frame:
            frame["source_currency"] = "XOF"
        result[measure] = frame
    return result


# The bundled sample CSVs are entirely synthetic (see
# src.db.seed_demo.generate_synthetic_oracle_views) and are written as
# plain UTF-8 — unlike a genuine Oracle client export, which lands in
# latin-1/cp1252 and would need `encoding="latin1"` on load.
SYNTHETIC_SAMPLE_DIR = "data/import/oracle_views_sample"


def run_oracle_views_sample_pipeline(
    year_from: int = 2020,
    year_to: int = 2026,
    sample_dir: str | Path = SYNTHETIC_SAMPLE_DIR,
    granularity: str = "annual",
) -> OracleViewsRunResult:
    """Runs the pre-allocated-views pipeline against a fabricated CSV
    export in the exact PBI_JDE column layout (see
    src.db.seed_demo.generate_synthetic_oracle_views) — a synthetic
    stand-in for a live Oracle extract, used for local validation and CI
    without any database connection. Regenerates the sample on each call
    so it always matches the requested year range and granularity."""
    from src.db.seed_demo import generate_synthetic_oracle_views

    create_schema()
    generate_synthetic_oracle_views(sample_dir, year_from, year_to, granularity)
    profile_path = "config/sources/oracle_pbi_views.yaml"
    profile = load_yaml(profile_path)
    frames = load_csv_frames(sample_dir)
    # Illustrative rate solely for local/CI validation; the live Oracle path
    # (ingest-oracle-views) loads approved rates from
    # config/fx/annual_rates.csv instead.
    FxRateRepository().upsert(
        FxRate(date(year_to, 12, 31), "XOF", base_currency(), 0.00128, "SAMPLE_ONLY", True)
    )
    return ingest_frames(frames, profile, year_from, year_to, "PBI_JDE", replace=True)
