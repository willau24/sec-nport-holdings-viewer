from decimal import Decimal

import pytest

from nport.errors import FilingParseError
from nport.models import IdentifierType
from nport.parser import meaningful, parse_filing, parse_header

ARGS = dict(
    cik="0000884394",
    source_url="https://example.test/primary_doc.xml",
    accession_number="0001410368-26-055357",
    filing_date="2026-05-28",
    form_type="NPORT-P",
)

def test_parses_holdings(spy_xml):
    filing = parse_filing(spy_xml, **ARGS)
    assert len(filing.holdings) == 8
    assert filing.registrant_name.startswith("State Street")

# repPdEnd is the fiscal year end and can be months after the period.
# Ex: SPY reports repPdDate=2026-03-31 and repPdEnd=2026-09-30
def test_period_end_prefers_reporting_date_over_fiscal_year_end(spy_xml):
    filing = parse_filing(spy_xml, **ARGS)
    assert filing.period_end == "2026-03-31"

def test_filler_series_name_normalizes_to_none(spy_xml):
    filing = parse_filing(spy_xml, **ARGS)
    assert filing.series_name is None
    assert filing.series_id is None

# Values must stay exact; float would introduce errors
def test_decimal_not_float(spy_xml):
    filing = parse_filing(spy_xml, **ARGS)
    holding = filing.holdings[0]
    assert isinstance(holding.value_usd, Decimal)
    assert isinstance(holding.balance, Decimal)

class TestIdentifierFallback:

    # 27 of SPY's 503 holdings are foreign-domiciled with no US CUSIP.
    def test_isin_fallback_for_foreign_issuers(self, spy_xml):
        filing = parse_filing(spy_xml, **ARGS)
        isins = [h for h in filing.holdings if h.identifier_type is IdentifierType.ISIN]
        assert len(isins) == 3
        assert any(h.identifier.startswith("IE00") for h in isins)

    def test_internal_id_fallback(self, pimco_xml):
        filing = parse_filing(pimco_xml, **ARGS)
        others = [h for h in filing.holdings if h.identifier_type is IdentifierType.OTHER]
        assert others
        assert others[0].identifier_desc == "Internal ID"

    def test_placeholder_never_surfaces(self, pimco_xml):
        filing = parse_filing(pimco_xml, **ARGS)
        assert all(h.identifier != "000000000" for h in filing.holdings)

# Negative valUSD are genuine short/derivative positions, not errors
def test_negative_values_preserved(pimco_xml):
    filing = parse_filing(pimco_xml, **ARGS)
    negatives = [h for h in filing.holdings if h.value_usd and h.value_usd < 0]
    assert negatives, "fixture should contain negative-value holdings"
    assert all(h.value_usd < 0 for h in negatives)

def test_total_value_is_net_of_negatives(pimco_xml):
    filing = parse_filing(pimco_xml, **ARGS)
    expected = sum(
        (h.value_usd for h in filing.holdings if h.value_usd is not None), Decimal("0")
    )
    assert filing.total_value == expected

# Sometimes derivatives often carry the literal string "N/A" as their name
def test_na_name_falls_back(pimco_xml):
    filing = parse_filing(pimco_xml, **ARGS)
    assert all(h.name != "N/A" for h in filing.holdings)
    assert all(h.name for h in filing.holdings)

def test_parse_header_skips_holdings(pimco_xml):
    header = parse_header(pimco_xml)
    assert header["seriesName"] == "PIMCO Income Fund"
    assert header["repPdDate"] == "2026-03-31"


def test_malformed_xml_raises():
    with pytest.raises(FilingParseError):
        parse_filing(b"<not-nport><unclosed>", **ARGS)

@pytest.mark.parametrize(
    "value,expected",
    [("N/A", None), ("n/a", None), ("  ", None), (None, None), ("Real Fund", "Real Fund")],
)
def test_meaningful(value, expected):
    assert meaningful(value) == expected
