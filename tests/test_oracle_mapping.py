from __future__ import annotations

import pytest

from src.adapters.oracle_source_mapping import (
    ORACLE_SOURCE_MAPPING,
    filterable_columns,
    known_views,
    measure_type_for,
)
from src.common.errors import ConfigurationError
from src.common.identifiers import safe_oracle_identifier


def test_all_five_views_are_known():
    assert set(known_views()) == {
        "ADIRECTE_COUT", "AINDIRECTE_COUT", "COUT_PAR_FCC",
        "CHARGES_REPARTIES", "RECETTE_PF",
    }


def test_recette_pf_maps_compte_to_account():
    columns = ORACLE_SOURCE_MAPPING["RECETTE_PF"]["columns"]
    assert columns["COMPTE"] == "account"
    assert measure_type_for("RECETTE_PF") == "SERVICE_REVENUE"


def test_cout_par_fcc_uses_singular_family_columns():
    columns = ORACLE_SOURCE_MAPPING["COUT_PAR_FCC"]["columns"]
    assert columns["FAMILLE"] == "family"
    assert columns["SOUS_FAMILLE"] == "subfamily"
    assert "FAMILLES" not in columns


def test_charges_reparties_uses_plural_family_columns_harmonised_to_same_fields():
    columns = ORACLE_SOURCE_MAPPING["CHARGES_REPARTIES"]["columns"]
    assert columns["FAMILLES"] == "family"
    assert columns["SOUS_FAMILLES"] == "subfamily"
    assert "FAMILLE" not in columns
    assert "SOUS_FAMILLE" not in columns
    # Same internal fields as COUT_PAR_FCC despite the different Oracle names.
    assert measure_type_for("CHARGES_REPARTIES") == measure_type_for("COUT_PAR_FCC")
    assert measure_type_for("CHARGES_REPARTIES") == "COST_CENTRE_COST"


def test_adirecte_cout_and_aindirecte_cout_measures():
    assert measure_type_for("ADIRECTE_COUT") == "DIRECT_ALLOCATION"
    assert measure_type_for("AINDIRECTE_COUT") == "INDIRECT_ALLOCATION"
    # AINDIRECTE_COUT has no cost-centre column (documented source limitation).
    assert "CODE_CC" not in ORACLE_SOURCE_MAPPING["AINDIRECTE_COUT"]["columns"]


def test_filterable_columns_only_come_from_the_mapping():
    assert filterable_columns("RECETTE_PF") == {
        "ANNEE", "CATEGORIE", "PRODUIT_FINI", "COMPTE", "MONTANT",
    }


@pytest.mark.parametrize(
    "bad_name",
    [
        "CODE_CC; DROP TABLE users",
        "CODE_CC --comment",
        "CODE CC",
        "CODE_CC'",
        "1CODE_CC",
        "CODE_CC\x00",
    ],
)
def test_safe_oracle_identifier_rejects_unsafe_input(bad_name):
    with pytest.raises(ConfigurationError):
        safe_oracle_identifier(bad_name, "column")


@pytest.mark.parametrize("good_name", ["CODE_CC", "ANNEE", "PRODUIT_FINI", "SOUS_FAMILLE"])
def test_safe_oracle_identifier_accepts_known_columns(good_name):
    assert safe_oracle_identifier(good_name, "column") == good_name
