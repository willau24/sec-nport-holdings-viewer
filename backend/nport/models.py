from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class IdentifierType(str, Enum):
    # Filings use the placeholder CUSIP `000000000` for securities without one
    # The real identifier is found in the <identifiers> element.
    CUSIP = "cusip"
    ISIN = "isin"
    TICKER = "ticker"
    OTHER = "other"
    NONE = "none"


@dataclass(frozen=True)
class Holding:
    identifier: str
    identifier_type: IdentifierType
    name: str
    title: str
    balance: Decimal | None
    units: str | None
    value_usd: Decimal | None
    pct_val: Decimal | None
    currency: str | None
    # Present only when identifier_type is OTHER
    identifier_desc: str | None = None

# A reference to one N-PORT filing.
# One CIK may have many of these sharing a filing date: one per fund series
@dataclass(frozen=True)
class FilingRef:
    cik: str
    accession_number: str
    filing_date: str
    report_date: str
    form_type: str
    primary_document: str

    @property
    def accession_no_dashes(self) -> str:
        return self.accession_number.replace("-", "")


# A fund series within a filing
@dataclass(frozen=True)
class SeriesRef:
    series_id: str | None
    series_name: str | None
    filing: FilingRef

# A fully parsed N-PORT filing
@dataclass
class Filing:
    cik: str
    registrant_name: str | None
    series_name: str | None
    series_id: str | None
    filing_date: str
    period_end: str | None
    accession_number: str
    form_type: str
    source_url: str
    total_assets: Decimal | None
    net_assets: Decimal | None
    holdings: list[Holding] = field(default_factory=list)

    @property
    def total_value(self) -> Decimal:
        return sum(
            (h.value_usd for h in self.holdings if h.value_usd is not None),
            Decimal("0"),
        )
