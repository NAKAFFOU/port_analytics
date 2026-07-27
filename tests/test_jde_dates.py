from datetime import date

import pytest

pytest.importorskip("oracledb")
from src.adapters.jde_oracle import date_to_jde_cyyddd, jde_cyyddd_to_date


def test_jde_date_round_trip():
    original = date(2025, 6, 24)
    encoded = date_to_jde_cyyddd(original)
    assert encoded == 125175
    assert jde_cyyddd_to_date(encoded) == original
