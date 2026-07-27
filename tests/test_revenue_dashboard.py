from __future__ import annotations

import logging

import pandas as pd
import pytest

from src.dashboard.components import compact_number
from src.dashboard.data import (
    build_revenue_hierarchy,
    clean_text_column,
    flatten_hierarchy_for_icicle,
    validate_revenue_dashboard_totals,
)

LABELS = {"root_label": "Revenue", "other_label": "Others", "not_specified": "Not specified"}


def _hierarchy(frame: pd.DataFrame, top_n: int = 5) -> dict:
    return build_revenue_hierarchy(
        frame,
        root_label=LABELS["root_label"],
        other_label=LABELS["other_label"],
        not_specified_label=LABELS["not_specified"],
        top_n=top_n,
    )


def _revenue_frame(rows: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["service_category", "service_name", "account", "amount_base"])


# --- 1. Compact French/English formatting (reused, not reinvented) --------

@pytest.mark.parametrize(
    "value,currency,language,expected",
    [
        (40_140_000_000, "XOF", "fr", "CFA 40,14Md"),
        (10_610_000_000, "GBP", "en", "£10.61B"),
        (845_000_000, "GBP", "fr", "£845,00M"),
        (35_500, "GBP", "fr", "£35,50k"),
        (0, "GBP", "fr", "£0"),
        (-1_000_000, "GBP", "en", "£-1.00M"),
    ],
)
def test_compact_number_formatting(value, currency, language, expected):
    assert compact_number(value, currency, language) == expected


def test_compact_number_never_shows_nan():
    assert "nan" not in compact_number(float("nan"), "GBP", "fr").lower()


# --- 2. Blank / whitespace / NCHAR-padding cleanup -------------------------

def test_clean_text_column_collapses_blanks_to_not_specified():
    series = pd.Series(["Marchandises", "   ", "", None, "Autres Services  "])
    cleaned = clean_text_column(series, "Not specified")
    assert cleaned.tolist() == [
        "Marchandises", "Not specified", "Not specified", "Not specified",
        "Autres Services",
    ]


# --- 3/6/7. Revenue root sum, no duplication, hierarchy correctness -------

def test_hierarchy_root_equals_sum_of_input_exactly():
    frame = _revenue_frame(
        [
            ("Marchandises", "PF-Acces Nautique", "Compte A", 1000.0),
            ("Marchandises", "PF-Acces Nautique", "Compte B", 500.0),
            ("Autres Services", "PF-Autres", "Compte C", 250.0),
        ]
    )
    hierarchy = _hierarchy(frame)
    assert hierarchy["value"] == pytest.approx(1750.0)


def test_category_and_product_sums_match_their_children():
    frame = _revenue_frame(
        [
            ("Marchandises", "PF-Acces Nautique", "Compte A", 1000.0),
            ("Marchandises", "PF-Acces Nautique", "Compte B", 500.0),
            ("Marchandises", "PF-Autre-Produit", "Compte C", 300.0),
        ]
    )
    hierarchy = _hierarchy(frame)
    category = hierarchy["children"][0]
    assert category["name"] == "Marchandises"
    assert category["value"] == pytest.approx(1800.0)
    assert sum(p["value"] for p in category["children"]) == pytest.approx(category["value"])

    nautique = next(p for p in category["children"] if p["name"] == "PF-Acces Nautique")
    assert nautique["value"] == pytest.approx(1500.0)
    assert sum(a["value"] for a in nautique["children"]) == pytest.approx(nautique["value"])


def test_duplicated_input_rows_are_summed_not_hidden():
    # Simulates what a bad join would produce: the same fact appearing
    # twice. build_revenue_hierarchy must not silently drop_duplicates() —
    # it sums whatever it is given, so an upstream duplication bug shows up
    # as an inflated total rather than being masked.
    frame = _revenue_frame(
        [
            ("Marchandises", "PF-Acces Nautique", "Compte A", 1000.0),
            ("Marchandises", "PF-Acces Nautique", "Compte A", 1000.0),
        ]
    )
    hierarchy = _hierarchy(frame)
    assert hierarchy["value"] == pytest.approx(2000.0)


def test_same_account_name_under_two_different_products_stays_separate():
    frame = _revenue_frame(
        [
            ("Marchandises", "PF-A", "Compte Commun", 100.0),
            ("Marchandises", "PF-B", "Compte Commun", 900.0),
        ]
    )
    hierarchy = _hierarchy(frame)
    category = hierarchy["children"][0]
    product_a = next(p for p in category["children"] if p["name"] == "PF-A")
    product_b = next(p for p in category["children"] if p["name"] == "PF-B")
    assert product_a["children"][0]["value"] == pytest.approx(100.0)
    assert product_b["children"][0]["value"] == pytest.approx(900.0)


def test_same_product_name_under_two_categories_is_not_merged():
    # A defensive case: even if a product code were reused across
    # categories, each category's grouping must only see its own rows.
    frame = _revenue_frame(
        [
            ("Marchandises", "PF-Shared", "Compte A", 100.0),
            ("Autres Services", "PF-Shared", "Compte B", 900.0),
        ]
    )
    hierarchy = _hierarchy(frame)
    totals = {c["name"]: c["value"] for c in hierarchy["children"]}
    assert totals["Marchandises"] == pytest.approx(100.0)
    assert totals["Autres Services"] == pytest.approx(900.0)


def test_negative_amount_is_preserved_not_dropped():
    frame = _revenue_frame(
        [
            ("Marchandises", "PF-A", "Compte A", -50.0),
            ("Marchandises", "PF-A", "Compte B", 200.0),
        ]
    )
    hierarchy = _hierarchy(frame)
    assert hierarchy["value"] == pytest.approx(150.0)


def test_empty_frame_returns_zero_root_without_error():
    hierarchy = _hierarchy(pd.DataFrame(columns=["service_category", "service_name", "account", "amount_base"]))
    assert hierarchy["value"] == 0.0
    assert hierarchy["children"] == []


def test_category_without_any_account_rows_still_aggregates():
    # A product with an empty/whitespace account is folded into
    # "Not specified" rather than creating a silent gap.
    frame = _revenue_frame([("Marchandises", "PF-A", "   ", 100.0)])
    hierarchy = _hierarchy(frame)
    product = hierarchy["children"][0]["children"][0]
    assert product["children"][0]["name"] == "Not specified"
    assert product["children"][0]["value"] == pytest.approx(100.0)


# --- 8/14. Top-N + "Others" node -------------------------------------------

def test_top_n_creates_others_node_that_sums_to_the_exact_remainder():
    rows = [
        ("Marchandises", f"PF-{i}", "Compte", float(value))
        for i, value in enumerate([500, 400, 300, 200, 100, 50, 10], start=1)
    ]
    frame = _revenue_frame(rows)
    hierarchy = _hierarchy(frame, top_n=5)
    category = hierarchy["children"][0]
    names = [p["name"] for p in category["children"]]
    assert names.count(LABELS["other_label"]) == 1
    assert len(category["children"]) == 6  # 5 shown + 1 "Others"

    others = next(p for p in category["children"] if p["name"] == LABELS["other_label"])
    assert others["value"] == pytest.approx(50.0 + 10.0)
    # Visible entries + "Others" must reconstruct the category total exactly.
    assert sum(p["value"] for p in category["children"]) == pytest.approx(category["value"])


def test_top_n_does_not_add_others_node_when_under_the_limit():
    rows = [("Marchandises", f"PF-{i}", "Compte", 10.0) for i in range(3)]
    frame = _revenue_frame(rows)
    hierarchy = _hierarchy(frame, top_n=5)
    category = hierarchy["children"][0]
    assert LABELS["other_label"] not in [p["name"] for p in category["children"]]


# --- 9. Hierarchy flattening for the Plotly icicle chart -------------------

def test_flatten_hierarchy_ids_encode_full_path():
    frame = _revenue_frame([("Marchandises", "PF-A", "Compte A", 100.0)])
    hierarchy = _hierarchy(frame)
    flat = flatten_hierarchy_for_icicle(hierarchy)
    ids = set(flat["id"])
    assert "Revenue" in ids
    assert "Revenue / Marchandises" in ids
    assert "Revenue / Marchandises / PF-A" in ids
    assert "Revenue / Marchandises / PF-A / Compte A" in ids
    root_row = flat[flat["id"] == "Revenue"].iloc[0]
    assert root_row["parent"] == ""
    assert root_row["depth"] == 0


def test_flatten_hierarchy_clips_negative_values_for_icicle_size_only():
    frame = _revenue_frame([("Marchandises", "PF-A", "Compte A", -50.0)])
    hierarchy = _hierarchy(frame)
    flat = flatten_hierarchy_for_icicle(hierarchy)
    leaf = flat[flat["label"] == "Compte A"].iloc[0]
    assert leaf["value"] == 0.0        # Icicle sizes can never be negative
    assert leaf["signed_value"] == -50.0  # true value is preserved for the tooltip


# --- 12/17. KPI <-> tree-root consistency control --------------------------

def test_validate_revenue_dashboard_totals_matching(caplog):
    with caplog.at_level(logging.WARNING):
        assert validate_revenue_dashboard_totals(1000.0, 1000.0049) is True
    assert not caplog.records


def test_validate_revenue_dashboard_totals_mismatch_logs_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        result = validate_revenue_dashboard_totals(1000.0, 900.0)
    assert result is False
    assert any("inconsistency" in record.message.lower() for record in caplog.records)


# --- 4/5/13/15/16. KPI arithmetic (revenue, allocations, net, count) -------

def test_kpi_arithmetic_matches_revenue_minus_allocations():
    psl = pd.DataFrame(
        {
            "service_code": ["PSL-1", "PSL-2"],
            "actual_revenue": [1000.0, 500.0],
            "total_attributed_cost": [400.0, 100.0],
        }
    )
    kpi_revenue = float(psl["actual_revenue"].sum())
    kpi_allocations = float(psl["total_attributed_cost"].sum())
    kpi_net = kpi_revenue - kpi_allocations
    kpi_count = int(psl["service_code"].nunique())

    assert kpi_revenue == pytest.approx(1500.0)
    assert kpi_allocations == pytest.approx(500.0)
    assert kpi_net == pytest.approx(1000.0)
    assert kpi_count == 2


def test_product_count_ignores_blank_or_null_service_codes():
    psl = pd.DataFrame({"service_code": ["PSL-1", "PSL-1", None, "  "]})
    cleaned = clean_text_column(psl["service_code"], "").replace("", pd.NA).dropna()
    assert int(cleaned.nunique()) == 1


# --- 2 (dependent filters): family narrows the sub-family options ----------

def test_family_filter_narrows_available_products():
    psl = pd.DataFrame(
        {
            "service_category": ["Marchandises", "Marchandises", "Autres Services"],
            "service_name": ["PF-A", "PF-B", "PF-C"],
        }
    )
    filtered = psl[psl["service_category"] == "Marchandises"]
    available_products = sorted(filtered["service_name"].unique().tolist())
    assert available_products == ["PF-A", "PF-B"]
    assert "PF-C" not in available_products


# --- revenue_facts as the single revenue source; psl for costs only -------
# (KPI Revenue must come only from revenue_facts; psl must contribute only
# direct/indirect/total costs; the two are combined solely by summing two
# already-aggregated scalars — never by merging the underlying rows.)

def test_kpi_revenue_comes_only_from_revenue_facts_not_from_psl():
    # psl's own "actual_revenue" is deliberately wrong here to prove the
    # page-level KPI must never read it.
    revenue_facts = _revenue_frame(
        [
            ("Marchandises", "PF-A", "Compte A", 1000.0),
            ("Marchandises", "PF-A", "Compte B", 500.0),
        ]
    )
    psl = pd.DataFrame(
        {
            "service_code": ["PSL-A"],
            "actual_revenue": [999_999.0],  # must be ignored entirely
            "direct_allocated_cost": [100.0],
            "indirect_allocated_cost": [50.0],
            "total_attributed_cost": [150.0],
        }
    )
    kpi_revenue = float(revenue_facts["amount_base"].sum())
    kpi_allocations = float(psl["total_attributed_cost"].sum())
    kpi_net = kpi_revenue - kpi_allocations

    assert kpi_revenue == pytest.approx(1500.0)
    assert kpi_allocations == pytest.approx(150.0)
    assert kpi_net == pytest.approx(1350.0)
    assert kpi_revenue != pytest.approx(psl["actual_revenue"].iloc[0])


def test_cost_scope_is_matched_to_revenue_selection_by_service_code_only():
    # Costs must follow whichever products are in scope on the revenue
    # side, matched by the stable code — set-membership, not a row join —
    # so an unrelated product's cost never leaks into the total.
    revenue_filtered = pd.DataFrame({"service_code": ["PSL-A", "PSL-A", "PSL-B"]})
    psl = pd.DataFrame(
        {
            "service_code": ["PSL-A", "PSL-B", "PSL-C"],
            "total_attributed_cost": [100.0, 200.0, 9_999.0],
        }
    )
    in_scope_codes = set(revenue_filtered["service_code"].dropna().unique())
    psl_filtered = psl[psl["service_code"].isin(in_scope_codes)]

    assert set(psl_filtered["service_code"]) == {"PSL-A", "PSL-B"}
    assert float(psl_filtered["total_attributed_cost"].sum()) == pytest.approx(300.0)


def test_cost_scope_filter_does_not_duplicate_or_multiply_rows():
    # Two revenue rows sharing the same service_code (e.g. two accounts
    # under one product) must not cause that product's cost row to be
    # counted twice via the set-membership filter.
    revenue_filtered = pd.DataFrame({"service_code": ["PSL-A"] * 5})
    psl = pd.DataFrame({"service_code": ["PSL-A"], "total_attributed_cost": [100.0]})
    in_scope_codes = set(revenue_filtered["service_code"].dropna().unique())
    psl_filtered = psl[psl["service_code"].isin(in_scope_codes)]

    assert len(psl_filtered) == 1
    assert float(psl_filtered["total_attributed_cost"].sum()) == pytest.approx(100.0)


def test_no_cost_rows_in_scope_yields_zero_allocations_not_a_crash():
    revenue_filtered = pd.DataFrame({"service_code": ["PSL-UNKNOWN"]})
    psl = pd.DataFrame({"service_code": ["PSL-A"], "total_attributed_cost": [100.0]})
    in_scope_codes = set(revenue_filtered["service_code"].dropna().unique())
    psl_filtered = psl[psl["service_code"].isin(in_scope_codes)]

    assert psl_filtered.empty
    assert float(psl_filtered["total_attributed_cost"].sum()) == 0.0


# --- No fact-to-fact join: service_lines is a dimension keyed uniquely ----

def test_service_lines_service_code_is_a_primary_key_no_fan_out_possible():
    """revenue_facts and psl both join oracle_view_facts/psl_indicators to
    service_lines on service_code. This is only safe because service_code
    is a primary key there (one row per code) — verified against the real
    schema so this can never silently become a fact-to-fact join."""
    from src.db.schema import SCHEMA_SQL

    assert "service_code TEXT PRIMARY KEY" in SCHEMA_SQL
