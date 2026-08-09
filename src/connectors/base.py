from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class SourceConnector(ABC):
    @abstractmethod
    def test_connection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def query_dataframe(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        raise NotImplementedError
