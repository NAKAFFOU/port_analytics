from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.common.config import base_currency
from src.currency.repository import FxRateRepository


@dataclass(frozen=True)
class ConversionResult:
    amount: float
    rate: float
    rate_date: date
    from_currency: str
    to_currency: str
    provider: str


class CurrencyConverter:
    """Converts through the configured analytical base currency.

    Stored rates are defined as: 1 unit of from_currency = rate units of
    to_currency. The package normally stores source-currency -> GBP rates.
    """

    def __init__(self, repository: FxRateRepository | None = None):
        self.repository = repository or FxRateRepository()
        self.base = base_currency()

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate_date: date,
    ) -> ConversionResult:
        source = from_currency.upper()
        target = to_currency.upper()
        if source == target:
            return ConversionResult(
                float(amount), 1.0, rate_date, source, target, "IDENTITY"
            )

        if target == self.base:
            fx = self.repository.get_latest_on_or_before(
                source, self.base, rate_date
            )
            return ConversionResult(
                amount * fx.rate,
                fx.rate,
                fx.rate_date,
                source,
                target,
                fx.provider,
            )

        if source == self.base:
            target_to_base = self.repository.get_latest_on_or_before(
                target, self.base, rate_date
            )
            inverse = 1.0 / target_to_base.rate
            return ConversionResult(
                amount * inverse,
                inverse,
                target_to_base.rate_date,
                source,
                target,
                target_to_base.provider,
            )

        source_to_base = self.repository.get_latest_on_or_before(
            source, self.base, rate_date
        )
        target_to_base = self.repository.get_latest_on_or_before(
            target, self.base, rate_date
        )
        cross_rate = source_to_base.rate / target_to_base.rate
        selected_date = min(
            source_to_base.rate_date, target_to_base.rate_date
        )
        provider = f"{source_to_base.provider}|{target_to_base.provider}"
        return ConversionResult(
            amount * cross_rate,
            cross_rate,
            selected_date,
            source,
            target,
            provider,
        )

    def convert_annual_flow(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        year: int,
        policy: str = "ANNUAL_AVERAGE",
    ) -> ConversionResult:
        source = from_currency.upper()
        target = to_currency.upper()
        year_end = date(year, 12, 31)
        if source == target:
            return ConversionResult(
                float(amount), 1.0, year_end, source, target, "IDENTITY"
            )

        policy = policy.upper()
        if policy == "YEAR_END":
            return self.convert(amount, source, target, year_end)
        if policy != "ANNUAL_AVERAGE":
            raise ValueError(f"Unsupported annual FX policy: {policy}")

        if target == self.base:
            fx = self.repository.get_annual_average(
                source, self.base, year
            )
            return ConversionResult(
                amount * fx.rate,
                fx.rate,
                fx.rate_date,
                source,
                target,
                fx.provider,
            )

        if source == self.base:
            fx = self.repository.get_annual_average(
                target, self.base, year
            )
            inverse = 1.0 / fx.rate
            return ConversionResult(
                amount * inverse,
                inverse,
                fx.rate_date,
                source,
                target,
                fx.provider,
            )

        source_to_base = self.repository.get_annual_average(
            source, self.base, year
        )
        target_to_base = self.repository.get_annual_average(
            target, self.base, year
        )
        cross_rate = source_to_base.rate / target_to_base.rate
        return ConversionResult(
            amount * cross_rate,
            cross_rate,
            year_end,
            source,
            target,
            f"{source_to_base.provider}|{target_to_base.provider}",
        )
