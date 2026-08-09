from __future__ import annotations

import argparse

from src.pipeline.kpi import compute_and_store_kpis
from src.rules.alerts import generate_alerts


def run_analytical_pipeline() -> tuple[int, int, int]:
    occ_count, psl_count = compute_and_store_kpis()
    alert_count = generate_alerts()
    print(f"Pipeline complete | OCC={occ_count} | PSL={psl_count} | Alerts={alert_count}")
    return occ_count, psl_count, alert_count


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Port Analytics pipeline runner")
    parser.add_argument(
        "--source",
        choices=["synthetic", "oracle"],
        default=None,
        help="Data source to run. Defaults to the DATA_SOURCE env var, or 'synthetic'.",
    )
    parser.add_argument("--year", type=int, default=None, help="Single reporting year (Oracle source).")
    parser.add_argument("--year-from", type=int, default=None, help="Overrides --year for the start of a range (Oracle source).")
    parser.add_argument("--year-to", type=int, default=None, help="Overrides --year for the end of a range (Oracle source).")
    parser.add_argument(
        "--object", dest="object_name", default=None,
        help="Restrict extraction to a single view or measure, e.g. RECETTE_PF or SERVICE_REVENUE (Oracle source).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Row limit for extraction, useful for a quick smoke test (Oracle source).")
    return parser


def _run_synthetic() -> None:
    from src.db.seed_demo import seed_demo

    seed_demo()
    run_analytical_pipeline()


def _run_oracle(year: int | None, year_from: int | None, year_to: int | None,
                object_name: str | None, limit: int | None) -> None:
    from src.adapters.oracle_pbi_views import OraclePBIViewsAdapter
    from src.common.config import get_settings
    from src.common.errors import ConfigurationError, PortAnalyticsError
    from src.ingestion.oracle_views import run_oracle_views_ingestion

    settings = get_settings()
    profile_path = settings["source"]["active_profile"]

    try:
        adapter = OraclePBIViewsAdapter(profile_path)
        connection_ok = adapter.test_connection()
    except ConfigurationError as exc:
        raise SystemExit(
            f"Oracle is not configured: {exc}. Fill in the required "
            "ORACLE_* variables in .env (see .env.example) before running "
            "--source oracle."
        ) from exc
    except PortAnalyticsError as exc:
        raise SystemExit(f"Oracle connection test failed: {exc}") from exc

    if not connection_ok:
        raise SystemExit(
            "Oracle connection test failed; aborting before extraction "
            "(no analytical recompute runs on a failed connection)."
        )

    resolved_from = year_from or year or settings["pipeline"]["reporting_year"]
    resolved_to = year_to or year or resolved_from

    result = run_oracle_views_ingestion(
        resolved_from,
        resolved_to,
        profile_path,
        replace=True,
        limit=limit,
        only_object=object_name,
    )
    print(result)
    if result.facts_loaded == 0:
        raise SystemExit(
            "No facts were loaded from Oracle; the analytical tables were "
            "reset but contain no data for the requested filters."
        )


def main(argv: list[str] | None = None) -> None:
    from src.common.config import env_optional

    args = _build_parser().parse_args(argv)
    source = (args.source or env_optional("DATA_SOURCE", "synthetic") or "synthetic").lower()

    if source == "synthetic":
        _run_synthetic()
    elif source == "oracle":
        _run_oracle(args.year, args.year_from, args.year_to, args.object_name, args.limit)
    else:
        raise SystemExit(f"Unknown --source: {source!r} (expected 'synthetic' or 'oracle')")


if __name__ == "__main__":
    main()
