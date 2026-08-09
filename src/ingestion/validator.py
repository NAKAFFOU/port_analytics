from __future__ import annotations

import pandas as pd

from src.common.errors import DataValidationError

REQUIRED_ACCOUNTING_COLUMNS = {
    "source_row_id",
    "company_code",
    "business_unit",
    "object_account",
    "subsidiary",
    "transaction_date",
    "amount_source",
    "source_currency",
}


def validate_accounting_frame(frame: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_ACCOUNTING_COLUMNS - set(frame.columns))
    if missing:
        raise DataValidationError(f"Missing canonical columns: {missing}")
    if frame.empty:
        return
    if frame["source_row_id"].isna().any():
        raise DataValidationError("source_row_id contains null values")
    if frame["transaction_date"].isna().any():
        raise DataValidationError("transaction_date contains null values")
    if pd.to_numeric(frame["amount_source"], errors="coerce").isna().any():
        raise DataValidationError("amount_source contains non-numeric values")
    if frame["source_currency"].fillna("").str.strip().eq("").any():
        raise DataValidationError("source_currency contains blank values")
