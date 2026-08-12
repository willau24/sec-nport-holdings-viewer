from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_serializer
from .models import Filing, Holding, SeriesRef

# Render a Decimal without scientific notation
def _plain(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")

class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    identifier: str
    identifier_type: str
    identifier_desc: str | None = None
    name: str
    title: str
    balance: Decimal | None
    units: str | None
    value_usd: Decimal | None
    pct_val: Decimal | None
    currency: str | None

    @field_serializer("balance", "value_usd", "pct_val")
    def _ser_decimal(self, value: Decimal | None) -> str | None:
        return _plain(value)

    @classmethod
    def from_holding(cls, holding: Holding) -> HoldingOut:
        return cls(
            identifier=holding.identifier,
            identifier_type=holding.identifier_type.value,
            identifier_desc=holding.identifier_desc,
            name=holding.name,
            title=holding.title,
            balance=holding.balance,
            units=holding.units,
            value_usd=holding.value_usd,
            pct_val=holding.pct_val,
            currency=holding.currency,
        )

# A resolved filing and its holdings.
class HoldingsResponse(BaseModel):
    requires_series_selection: bool = False

    cik: str
    registrant_name: str | None
    series_name: str | None
    series_id: str | None
    filing_date: str
    period_end: str | None
    accession_number: str
    form_type: str
    source_url: str
    total_value: Decimal
    total_assets: Decimal | None
    net_assets: Decimal | None
    holdings_count: int
    holdings: list[HoldingOut]

    @field_serializer("total_value", "total_assets", "net_assets")
    def _ser_decimal(self, value: Decimal | None) -> str | None:
        return _plain(value)

    @classmethod
    def from_filing(cls, filing: Filing) -> HoldingsResponse:
        return cls(
            cik=filing.cik,
            registrant_name=filing.registrant_name,
            series_name=filing.series_name,
            series_id=filing.series_id,
            filing_date=filing.filing_date,
            period_end=filing.period_end,
            accession_number=filing.accession_number,
            form_type=filing.form_type,
            source_url=filing.source_url,
            total_value=filing.total_value,
            total_assets=filing.total_assets,
            net_assets=filing.net_assets,
            holdings_count=len(filing.holdings),
            holdings=[HoldingOut.from_holding(h) for h in filing.holdings],
        )


class SeriesOut(BaseModel):
    series_id: str | None
    series_name: str | None
    accession_number: str
    filing_date: str

    @classmethod
    def from_series(cls, series: SeriesRef) -> SeriesOut:
        return cls(
            series_id=series.series_id,
            series_name=series.series_name,
            accession_number=series.filing.accession_number,
            filing_date=series.filing.filing_date,
        )

# Returned when a CIK maps to several funds and the caller must choose.
# It's 200 because the request succeeded, and the user must legitimately
# choose the fund.
class SeriesSelectionResponse(BaseModel):
    requires_series_selection: bool = True

    cik: str
    filing_date: str
    series_count: int
    series: list[SeriesOut]


class ErrorResponse(BaseModel):
    error: str
    detail: str
