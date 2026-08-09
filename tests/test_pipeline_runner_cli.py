from __future__ import annotations

import pytest

from src.cli import build_parser
from src.pipeline.runner import _build_parser as build_pipeline_parser


def test_pipeline_parser_defaults_to_no_explicit_source():
    args = build_pipeline_parser().parse_args([])
    assert args.source is None  # resolved from DATA_SOURCE env at runtime, default "synthetic"
    assert args.year is None
    assert args.object_name is None
    assert args.limit is None


def test_pipeline_parser_accepts_oracle_filters():
    args = build_pipeline_parser().parse_args(
        ["--source", "oracle", "--year", "2026", "--object", "RECETTE_PF", "--limit", "100"]
    )
    assert args.source == "oracle"
    assert args.year == 2026
    assert args.object_name == "RECETTE_PF"
    assert args.limit == 100


def test_pipeline_main_rejects_unknown_source():
    from src.pipeline.runner import main

    with pytest.raises(SystemExit):
        main(["--source", "not-a-real-source"])


def test_cli_ingest_oracle_views_accepts_object_and_limit():
    args = build_parser().parse_args(
        ["ingest-oracle-views", "--year-from", "2022", "--year-to", "2026",
         "--object", "COUT_PAR_FCC", "--limit", "50"]
    )
    assert args.year_from == 2022
    assert args.year_to == 2026
    assert args.object_name == "COUT_PAR_FCC"
    assert args.limit == 50


def test_cli_inspect_oracle_metadata_has_default_output_path():
    args = build_parser().parse_args(["inspect-oracle-metadata"])
    assert args.out == "data/export/oracle_metadata_report.json"
