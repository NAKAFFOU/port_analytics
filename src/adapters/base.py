from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class AccountingSourceAdapter(ABC):
    @abstractmethod
    def test_connection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def extract_accounting_transactions(self, date_from: date, date_to: date) -> pd.DataFrame:
        """Return the canonical accounting-transaction contract."""
        raise NotImplementedError
