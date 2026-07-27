from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from src.ingestion.oracle_views import _normalise_frame, _text, safe_amount, safe_year


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("2026", 2026),
        (2026, 2026),
        (2026.0, 2026),
        (Decimal("2026"), 2026),
        ("not-a-year", None),
        (float("nan"), None),
    ],
)
def test_safe_year(value, expected):
    assert safe_year(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("-100758179", -100758179.0),
        (Decimal("-100758179"), -100758179.0),
        ("1990600353", 1990600353.0),
        ("not-a-number", None),
    ],
)
def test_safe_amount_preserves_value_without_rescaling_or_sign_flip(value, expected):
    # Oracle already applies * -1, /100 and ROUND() inside the PBI_JDE views;
    # safe_amount must only parse, never rescale or invert the sign.
    result = safe_amount(value)
    assert result == expected
    if result is not None and value not in (None, "", "   "):
        assert abs(result) == abs(float(str(value)))


def test_text_trims_by_default(monkeypatch):
    monkeypatch.delenv("TRIM_ORACLE_TEXT", raising=False)
    assert _text("  Sample Department Name (ABC)   ") == "Sample Department Name (ABC)"


def test_text_does_not_trim_when_disabled(monkeypatch):
    monkeypatch.setenv("TRIM_ORACLE_TEXT", "false")
    assert _text("  padded  ") == "  padded  "


def test_text_preserves_none_as_default():
    assert _text(None, default="fallback") == "fallback"
    assert _text(pd.NA, default="fallback") == "fallback"


def test_normalise_frame_flags_missing_required_columns():
    frame = pd.DataFrame(
        {
            "reporting_year": ["2024", "", "2025"],
            "source_service_name": ["PF-Pilotage", "PF-Towage", ""],
            "amount_source": ["-1000", "-2000", "-3000"],
        }
    )
    grouped, issues, valid_rows = _normalise_frame(frame, "INDIRECT_ALLOCATION")
    assert valid_rows == 1  # only the first row has every required field
    assert any("reporting_year" in issue for issue in issues)
    assert any("source_service_name" in issue for issue in issues)
    assert not grouped.empty
    # INDIRECT_ALLOCATION is a cost measure (force_absolute=True): the
    # negative source value is displayed as a positive magnitude.
    assert grouped.iloc[0]["amount_source"] == 1000.0


def test_normalise_frame_never_rescales_amount_only_takes_absolute_value():
    frame = pd.DataFrame(
        {
            "reporting_year": ["2024"],
            "source_service_name": ["PF-Pilotage"],
            "amount_source": ["-100758179"],
        }
    )
    grouped, issues, valid_rows = _normalise_frame(frame, "INDIRECT_ALLOCATION")
    assert valid_rows == 1
    assert issues == []
    # Cost measures are shown as a positive magnitude (force_absolute), but
    # the /100 scaling and rounding done by Oracle must never be repeated.
    assert grouped.iloc[0]["amount_source"] == 100758179.0


def test_service_revenue_amount_keeps_its_natural_sign():
    # SERVICE_REVENUE has force_absolute=False: unlike cost measures, a
    # negative row (credit note/correction) must surface as-is, not be
    # silently flipped positive.
    frame = pd.DataFrame(
        {
            "reporting_year": ["2024"],
            "service_category": ["Marchandises"],
            "source_service_name": ["PF-Acces Nautique"],
            "account": ["Cession d'eau aux navires"],
            "amount_source": ["-500"],
        }
    )
    grouped, issues, valid_rows = _normalise_frame(frame, "SERVICE_REVENUE")
    assert valid_rows == 1
    assert grouped.iloc[0]["amount_source"] == -500.0


def test_cost_centre_cost_keeps_family_and_subfamily_as_distinct_dimensions():
    # Same centre/year, two different families: must NOT collapse into one
    # aggregated row (that would silently merge distinct cost lines).
    frame = pd.DataFrame(
        {
            "reporting_year": ["2024", "2024"],
            "source_cost_centre_code": ["1000", "1000"],
            "source_cost_centre_name": ["DIRECTION GENERALE", "DIRECTION GENERALE"],
            "family": ["Charges de personnel", "Prestations externes"],
            "subfamily": ["Salaires", "Autres prestataires"],
            "amount_source": ["-1000", "-2000"],
        }
    )
    grouped, issues, valid_rows = _normalise_frame(frame, "COST_CENTRE_COST")
    assert valid_rows == 2
    assert issues == []
    assert len(grouped) == 2
    assert set(grouped["family"]) == {"Charges de personnel", "Prestations externes"}
    # COST_CENTRE_COST is a cost measure (force_absolute=True).
    assert grouped["amount_source"].sum() == 3000.0


def test_cost_centre_cost_without_family_column_still_aggregates_by_centre():
    # Views/rows with no family (blank) must still work exactly as before —
    # this is the pre-existing head-office / unclassified cost-line case.
    frame = pd.DataFrame(
        {
            "reporting_year": ["2024", "2024"],
            "source_cost_centre_code": ["1000", "1000"],
            "source_cost_centre_name": ["DIRECTION GENERALE", "DIRECTION GENERALE"],
            "amount_source": ["-1000", "-2000"],
        }
    )
    grouped, issues, valid_rows = _normalise_frame(frame, "COST_CENTRE_COST")
    assert valid_rows == 2
    assert len(grouped) == 1
    assert grouped.iloc[0]["amount_source"] == 3000.0


def test_service_revenue_keeps_account_as_a_distinct_dimension():
    frame = pd.DataFrame(
        {
            "reporting_year": ["2024", "2024"],
            "service_category": ["Marchandises", "Marchandises"],
            "source_service_name": ["PF-Acces Nautique", "PF-Acces Nautique"],
            "account": ["Autres Serv vendus aux navires", "Cession d'eau aux navires"],
            "amount_source": ["1000", "2000"],
        }
    )
    grouped, issues, valid_rows = _normalise_frame(frame, "SERVICE_REVENUE")
    assert valid_rows == 2
    assert len(grouped) == 2
    assert set(grouped["account"]) == {
        "Autres Serv vendus aux navires", "Cession d'eau aux navires",
    }
