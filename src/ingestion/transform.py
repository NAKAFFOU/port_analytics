from __future__ import annotations

from datetime import date

from src.common.config import base_currency
from src.currency.converter import CurrencyConverter
from src.db.schema import connect
from src.ingestion.loader import add_quality_issue
from src.ingestion.mapping import find_account, find_cost_centre, find_service


def _ensure_period(transaction_date: str) -> str:
    parsed = date.fromisoformat(transaction_date)
    period_id = f"{parsed.year}-{parsed.month:02d}"
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM reporting_periods WHERE period_id=?", (period_id,)).fetchone()
    if row is None:
        raise ValueError(f"Reporting period not configured: {period_id}")
    return period_id


def transform_batch_to_core(batch_id: str) -> tuple[int, int]:
    converter = CurrencyConverter()
    loaded = 0
    rejected = 0
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM stg_accounting_transactions WHERE batch_id=? ORDER BY staging_id",
            (batch_id,),
        ).fetchall()

    for row in rows:
        source_system = row["source_system"]
        source_row_id = row["source_row_id"]
        tx_date = row["transaction_date"]
        account_map = find_account(source_system, row["company_code"], row["object_account"], row["subsidiary"], tx_date)
        if account_map is None:
            rejected += 1
            add_quality_issue(batch_id, source_system, source_row_id, "UNMAPPED_ACCOUNT", f"No account mapping for {row['company_code']}/{row['object_account']}/{row['subsidiary']}")
            continue

        signed_amount = float(row["amount_source"]) * float(account_map["sign_multiplier"])
        if signed_amount < 0:
            # The target analytical model stores positive cost and revenue magnitudes.
            signed_amount = abs(signed_amount)

        try:
            conversion = converter.convert(signed_amount, row["source_currency"], base_currency(), date.fromisoformat(tx_date))
        except Exception as exc:
            rejected += 1
            add_quality_issue(batch_id, source_system, source_row_id, "FX_RATE_MISSING", str(exc))
            continue

        period_id = _ensure_period(tx_date)
        nature = account_map["target_nature"]

        if nature == "COST":
            centre_map = find_cost_centre(source_system, row["company_code"], row["business_unit"], tx_date)
            if centre_map is None:
                rejected += 1
                add_quality_issue(batch_id, source_system, source_row_id, "UNMAPPED_COST_CENTRE", f"No cost-centre mapping for {row['company_code']}/{row['business_unit']}")
                continue
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO actual_transactions(
                        source_system,source_row_id,centre_code,category_code,period_id,transaction_date,
                        amount_source,source_currency,fx_rate_to_base,fx_rate_date,amount_base,base_currency,description
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source_system,source_row_id,centre_code,category_code)
                    DO UPDATE SET amount_source=excluded.amount_source,source_currency=excluded.source_currency,
                                  fx_rate_to_base=excluded.fx_rate_to_base,fx_rate_date=excluded.fx_rate_date,
                                  amount_base=excluded.amount_base,description=excluded.description
                    """,
                    (source_system, source_row_id, centre_map["target_code"], account_map["target_category"], period_id, tx_date, signed_amount, row["source_currency"], conversion.rate, conversion.rate_date.isoformat(), conversion.amount, base_currency(), row["description"]),
                )
        else:
            service_map = find_service(source_system, row["company_code"], row["business_unit"], row["object_account"], row["subsidiary"], tx_date)
            if service_map is None:
                rejected += 1
                add_quality_issue(batch_id, source_system, source_row_id, "UNMAPPED_SERVICE", f"No service mapping for {row['company_code']}/{row['business_unit']}/{row['object_account']}/{row['subsidiary']}")
                continue
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO revenue_transactions(
                        source_system,source_row_id,service_code,category_code,period_id,transaction_date,
                        amount_source,source_currency,fx_rate_to_base,fx_rate_date,amount_base,base_currency,description
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source_system,source_row_id,service_code,category_code)
                    DO UPDATE SET amount_source=excluded.amount_source,source_currency=excluded.source_currency,
                                  fx_rate_to_base=excluded.fx_rate_to_base,fx_rate_date=excluded.fx_rate_date,
                                  amount_base=excluded.amount_base,description=excluded.description
                    """,
                    (source_system, source_row_id, service_map["target_service_code"], account_map["target_category"], period_id, tx_date, signed_amount, row["source_currency"], conversion.rate, conversion.rate_date.isoformat(), conversion.amount, base_currency(), row["description"]),
                )
        loaded += 1

    return loaded, rejected
