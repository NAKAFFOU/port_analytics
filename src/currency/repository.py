from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from src.common.config import get_settings
from src.common.errors import MissingExchangeRateError
from src.db.schema import connect


@dataclass(frozen=True)
class FxRate:
    rate_date: date
    from_currency: str
    to_currency: str
    rate: float
    provider: str
    is_estimated: bool


class FxRateRepository:
    def upsert(self, fx_rate: FxRate) -> None:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO fx_rates(rate_date,from_currency,to_currency,rate,provider,is_estimated)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(rate_date,from_currency,to_currency,provider)
                DO UPDATE SET rate=excluded.rate,is_estimated=excluded.is_estimated,loaded_at=datetime('now')
                """,
                (
                    fx_rate.rate_date.isoformat(),
                    fx_rate.from_currency.upper(),
                    fx_rate.to_currency.upper(),
                    fx_rate.rate,
                    fx_rate.provider,
                    int(fx_rate.is_estimated),
                ),
            )

    def get_latest_on_or_before(self, from_currency: str, to_currency: str, rate_date: date) -> FxRate:
        source = from_currency.upper()
        target = to_currency.upper()
        if source == target:
            return FxRate(rate_date, source, target, 1.0, "IDENTITY", False)

        with connect() as conn:
            row = conn.execute(
                """
                SELECT rate_date,from_currency,to_currency,rate,provider,is_estimated
                FROM fx_rates
                WHERE from_currency=? AND to_currency=? AND rate_date<=?
                ORDER BY rate_date DESC, loaded_at DESC
                LIMIT 1
                """,
                (source, target, rate_date.isoformat()),
            ).fetchone()

        if row is None:
            raise MissingExchangeRateError(
                f"No FX rate for {source}->{target} on or before {rate_date.isoformat()}"
            )

        selected_date = date.fromisoformat(row["rate_date"])
        maximum_age = int(get_settings()["currency"].get("maximum_rate_age_days", 40))
        age = (rate_date - selected_date).days
        if age > maximum_age:
            raise MissingExchangeRateError(
                f"FX rate {source}->{target} is {age} days old; maximum allowed is {maximum_age}"
            )

        return FxRate(
            selected_date,
            row["from_currency"],
            row["to_currency"],
            float(row["rate"]),
            row["provider"],
            bool(row["is_estimated"]),
        )

    def get_annual_average(self, from_currency: str, to_currency: str, year: int) -> FxRate:
        source = from_currency.upper()
        target = to_currency.upper()
        year_end = date(year, 12, 31)
        if source == target:
            return FxRate(year_end, source, target, 1.0, "IDENTITY", False)

        with connect() as conn:
            row = conn.execute(
                """
                SELECT AVG(rate) AS average_rate,
                       COUNT(*) AS observation_count,
                       MAX(is_estimated) AS any_estimated,
                       GROUP_CONCAT(DISTINCT provider) AS providers
                FROM fx_rates
                WHERE from_currency=? AND to_currency=?
                  AND substr(rate_date,1,4)=?
                """,
                (source, target, str(year)),
            ).fetchone()

        if row is None or not row["observation_count"]:
            raise MissingExchangeRateError(
                f"No annual FX observations for {source}->{target} in {year}"
            )
        provider = f"ANNUAL_AVERAGE[{row['providers'] or 'UNKNOWN'}]"
        return FxRate(
            year_end,
            source,
            target,
            float(row["average_rate"]),
            provider,
            bool(row["any_estimated"]),
        )

    def currencies_for_target(self, to_currency: str) -> list[str]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT from_currency FROM fx_rates WHERE to_currency=? ORDER BY from_currency",
                (to_currency.upper(),),
            ).fetchall()
        values = [row[0] for row in rows]
        if to_currency.upper() not in values:
            values.append(to_currency.upper())
        return sorted(set(values))
