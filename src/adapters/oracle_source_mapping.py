from __future__ import annotations

from typing import Any

# Central Oracle -> internal-model column mapping for the PBI_JDE analytical
# views. This is the single source of truth used by:
#   - the metadata inspector (src/adapters/oracle_metadata.py), to validate
#     the real Oracle structure against what the pipeline expects;
#   - OraclePBIViewsAdapter, to build SELECT lists and validate optional
#     filter columns;
#   - future source adapters (SAP, Sage) that need to feed the same
#     internal model without the dashboard or pipeline changing.
#
# Internal field names intentionally match the columns already used by
# src/ingestion/oracle_views.py (reporting_year, source_cost_centre_code,
# source_cost_centre_name, service_category, source_service_name,
# amount_source) so existing pipeline code keeps working unchanged. `account`,
# `family` and `subfamily` are additional fields captured at this layer for
# views that expose them (RECETTE_PF.COMPTE, COUT_PAR_FCC/CHARGES_REPARTIES
# family columns); they are not yet threaded into oracle_view_facts.
ORACLE_SOURCE_MAPPING: dict[str, dict[str, Any]] = {
    "ADIRECTE_COUT": {
        "measure_type": "DIRECT_ALLOCATION",
        "columns": {
            "ANNEE": "reporting_year",
            "CODE_CC": "source_cost_centre_code",
            "CATEGORIE": "service_category",
            "PRODUIT_FINI": "source_service_name",
            "MONTANT": "amount_source",
        },
    },
    "AINDIRECTE_COUT": {
        "measure_type": "INDIRECT_ALLOCATION",
        "columns": {
            "ANNEE": "reporting_year",
            "CATEGORIE": "service_category",
            "PRODUIT_FINI": "source_service_name",
            "MONTANT": "amount_source",
        },
    },
    "COUT_PAR_FCC": {
        "measure_type": "COST_CENTRE_COST",
        "columns": {
            "ANNEE": "reporting_year",
            "CODE_CC": "source_cost_centre_code",
            "DESC_CC": "source_cost_centre_name",
            "FAMILLE": "family",
            "SOUS_FAMILLE": "subfamily",
            "MONTANT": "amount_source",
        },
    },
    "CHARGES_REPARTIES": {
        "measure_type": "COST_CENTRE_COST",
        "columns": {
            "ANNEE": "reporting_year",
            "CODE_CC": "source_cost_centre_code",
            "DESC_CC": "source_cost_centre_name",
            # Plural column names here, unlike COUT_PAR_FCC (FAMILLE/
            # SOUS_FAMILLE) — harmonised to the same internal fields.
            "FAMILLES": "family",
            "SOUS_FAMILLES": "subfamily",
            "MONTANT": "amount_source",
        },
    },
    "RECETTE_PF": {
        "measure_type": "SERVICE_REVENUE",
        "columns": {
            "ANNEE": "reporting_year",
            "CATEGORIE": "service_category",
            "PRODUIT_FINI": "source_service_name",
            "COMPTE": "account",
            "MONTANT": "amount_source",
        },
    },
}

# Oracle columns that are text-typed in at least one of the five views and
# therefore safe candidates for TRIM_ORACLE_TEXT / NCHAR-padding cleanup.
TEXT_COLUMNS = {
    "CODE_CC", "DESC_CC", "CATEGORIE", "PRODUIT_FINI", "COMPTE",
    "FAMILLE", "SOUS_FAMILLE", "FAMILLES", "SOUS_FAMILLES",
}

# Columns expected to be numeric (NUMBER-like) across the five views.
NUMERIC_COLUMNS = {"ANNEE", "MONTANT"}


def known_views() -> list[str]:
    return list(ORACLE_SOURCE_MAPPING)


def internal_columns(view: str) -> dict[str, str]:
    return ORACLE_SOURCE_MAPPING[view]["columns"]


def measure_type_for(view: str) -> str:
    return ORACLE_SOURCE_MAPPING[view]["measure_type"]


def filterable_columns(view: str) -> set[str]:
    """Oracle column names from `view` that may be used as optional bind
    filters. Column *names* are never taken from caller input — only from
    this mapping — so they can be safely interpolated into SQL identifiers.
    """
    return set(internal_columns(view))
