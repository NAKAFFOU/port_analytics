from __future__ import annotations

import argparse
from datetime import date

from src.common.config import get_settings, load_yaml
from src.common.errors import ConfigurationError, PortAnalyticsError
from src.common.logging_config import configure_logging
from src.currency.providers import load_manual_csv, refresh_ecb
from src.db.schema import create_schema, list_user_tables
from src.db.seed_demo import seed_demo
from src.ingestion.supplemental import load_activity_csv, load_budget_csv
from src.pipeline.runner import run_analytical_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Port Analytics multi-source prototype"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db")
    seed = commands.add_parser("seed-demo")
    seed.add_argument("--granularity", choices=["annual", "monthly"], default="monthly")
    seed.add_argument("--year-from", type=int, default=2020)
    seed.add_argument("--year-to", type=int, default=2026)
    commands.add_parser("run-pipeline")
    run_demo = commands.add_parser("run-demo")
    run_demo.add_argument("--granularity", choices=["annual", "monthly"], default="monthly")
    run_demo.add_argument("--year-from", type=int, default=2020)
    run_demo.add_argument("--year-to", type=int, default=2026)

    oracle_sample = commands.add_parser("run-oracle-views-sample")
    oracle_sample.add_argument("--year-from", type=int, default=2020)
    oracle_sample.add_argument("--year-to", type=int, default=2026)
    oracle_sample.add_argument("--granularity", choices=["annual", "monthly"], default="annual")
    oracle_sample.add_argument("--dir", dest="sample_dir", default="data/import/oracle_views_sample")
    commands.add_parser("test-connection")

    fx = commands.add_parser("load-fx")
    fx.add_argument("--file", default="config/fx/annual_rates.csv")

    ecb = commands.add_parser("refresh-ecb")
    ecb.add_argument("--latest-only", action="store_true")

    inspect = commands.add_parser("inspect-source")
    inspect.add_argument("--object", "--table", dest="object_name", required=True)

    probe = commands.add_parser("probe-oracle-views")
    probe.add_argument("--year", type=int, required=True)
    probe.add_argument("--limit", type=int, default=20)

    ingest_views = commands.add_parser("ingest-oracle-views")
    ingest_views.add_argument("--year-from", type=int, required=True)
    ingest_views.add_argument("--year-to", type=int, required=True)
    ingest_views.add_argument("--object", dest="object_name", default=None)
    ingest_views.add_argument("--limit", type=int, default=None)

    metadata = commands.add_parser("inspect-oracle-metadata")
    metadata.add_argument("--out", default="data/export/oracle_metadata_report.json")

    # Legacy direct-table adapter retained as an optional extension.
    ingest = commands.add_parser("ingest-jde")
    ingest.add_argument("--start", required=True)
    ingest.add_argument("--end", required=True)

    budgets = commands.add_parser("load-budgets")
    budgets.add_argument("--file", default="data/import/budgets.csv")

    activity = commands.add_parser("load-activity")
    activity.add_argument("--file", default="data/import/activity_volumes.csv")
    return parser


def _active_adapter():
    profile_path = get_settings()["source"]["active_profile"]
    profile = load_yaml(profile_path)
    if profile.get("adapter") == "oracle_pbi_views":
        from src.adapters.oracle_pbi_views import OraclePBIViewsAdapter
        return OraclePBIViewsAdapter(profile_path)
    from src.adapters.jde_oracle import JDEOracleAdapter
    return JDEOracleAdapter(profile_path)


def _print_probe(year: int, limit: int) -> None:
    from src.adapters.oracle_pbi_views import OraclePBIViewsAdapter

    profile_path = get_settings()["source"]["active_profile"]
    adapter = OraclePBIViewsAdapter(profile_path)
    frames = adapter.extract_all(year, year, limit=limit)
    for measure, frame in frames.items():
        print(f"\n=== {measure} ===")
        print(f"Rows returned: {len(frame)}")
        print("Columns:", list(frame.columns))
        if frame.empty:
            continue
        print(frame.head(limit).to_string(index=False))
        for column in [
            "service_category", "source_service_name",
            "source_cost_centre_code", "source_currency",
        ]:
            if column in frame.columns:
                values = frame[column].dropna().astype(str).str.strip().unique()[:20]
                print(f"Distinct {column}:", list(values))


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()

    if args.command == "init-db":
        create_schema()
        print(f"{len(list_user_tables())} user tables")
    elif args.command == "seed-demo":
        seed_demo(args.granularity, args.year_from, args.year_to)
    elif args.command == "run-pipeline":
        run_analytical_pipeline()
    elif args.command == "run-demo":
        seed_demo(args.granularity, args.year_from, args.year_to)
        run_analytical_pipeline()
    elif args.command == "run-oracle-views-sample":
        from src.ingestion.oracle_views import run_oracle_views_sample_pipeline
        print(
            run_oracle_views_sample_pipeline(
                args.year_from, args.year_to, args.sample_dir, args.granularity
            )
        )
    elif args.command == "load-fx":
        create_schema()
        print(f"Loaded {load_manual_csv(args.file)} FX rates")
    elif args.command == "refresh-ecb":
        create_schema()
        print(
            f"Loaded {refresh_ecb(use_90_days=not args.latest_only)} "
            "ECB observations"
        )
    elif args.command == "test-connection":
        try:
            adapter = _active_adapter()
        except ConfigurationError as exc:
            print(f"Configuration error: {exc}")
            print("Fill in the required variables in .env (see .env.example) and retry.")
            return
        try:
            ok = adapter.test_connection()
        except PortAnalyticsError as exc:
            print(f"Connection failed: {exc}")
            return
        print("Connection OK" if ok else "Connection failed")
        if not ok:
            return
        if hasattr(adapter, "describe_connection"):
            print("Session diagnostics:")
            for key, value in adapter.describe_connection().items():
                print(f"  {key}: {value}")
        if hasattr(adapter, "connector") and hasattr(adapter, "schema"):
            from src.adapters.oracle_metadata import inspect_all_views, print_report
            print(f"\nInspecting the 5 PBI_JDE views in schema {adapter.schema}:")
            print_report(inspect_all_views(adapter.connector, adapter.schema))
    elif args.command == "inspect-oracle-metadata":
        try:
            adapter = _active_adapter()
        except ConfigurationError as exc:
            raise SystemExit(f"Configuration error: {exc}") from exc
        if not hasattr(adapter, "schema"):
            raise SystemExit(
                "inspect-oracle-metadata requires the oracle_pbi_views "
                "adapter to be the active source profile."
            )
        from src.adapters.oracle_metadata import inspect_all_views, print_report, write_report
        reports = inspect_all_views(adapter.connector, adapter.schema)
        print_report(reports)
        path = write_report(reports, args.out)
        print(f"\nReport written to {path}")
    elif args.command == "inspect-source":
        adapter = _active_adapter()
        if hasattr(adapter, "inspect_view"):
            frame = adapter.inspect_view(args.object_name)
        else:
            from src.ingestion.source_inspector import inspect_source_object
            frame = inspect_source_object(args.object_name)
        print(frame.to_string(index=False))
    elif args.command == "probe-oracle-views":
        _print_probe(args.year, args.limit)
    elif args.command == "ingest-oracle-views":
        from src.ingestion.oracle_views import run_oracle_views_ingestion
        result = run_oracle_views_ingestion(
            args.year_from, args.year_to, replace=True,
            limit=args.limit, only_object=args.object_name,
        )
        print(result)
    elif args.command == "ingest-jde":
        from src.ingestion.runner import run_jde_ingestion
        create_schema()
        print(
            "Batch:",
            run_jde_ingestion(
                date.fromisoformat(args.start),
                date.fromisoformat(args.end),
            ),
        )
    elif args.command == "load-budgets":
        create_schema()
        print(
            "Loaded cost and revenue budgets:",
            load_budget_csv(args.file),
        )
    elif args.command == "load-activity":
        create_schema()
        print("Loaded activity rows:", load_activity_csv(args.file))


if __name__ == "__main__":
    main()
