"""Data models for NBP API responses."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)  # immutable — bezpieczniejsze
class ExchangeRate:
    """Single exchange rate observation from NBP API."""
    currency_code: str         # "USD"
    currency_name: str         # "dolar amerykański"
    effective_date: date       # 2026-05-27
    rate_pln: Decimal          # 4.0521 (PLN per 1 unit)
    table_no: str              # "100/A/NBP/2026"
    table: str                 # "A"


# Optional helper to build ExchangeRate from raw NBP JSON dict
def from_nbp_json(table_dict: dict, rate_dict: dict) -> ExchangeRate:
    """
    Construct ExchangeRate from NBP API JSON shapes.

    table_dict - outer object (has table, currency, code)
    rate_dict - single item from the 'rates' array (has no, effectiveDate, mid)
    """
    return ExchangeRate(
        currency_code=table_dict["code"],
        currency_name=table_dict["currency"],
        effective_date=date.fromisoformat(rate_dict["effectiveDate"]),
        # str() — uniknij float precision loss
        rate_pln=Decimal(str(rate_dict["mid"])),
        table_no=rate_dict["no"],
        table=table_dict["table"],
    )
