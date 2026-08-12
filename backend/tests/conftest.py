from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture(scope="session")
def spy_xml() -> bytes:
    """SPY: single series"""
    return (FIXTURES / "spy_nport.xml").read_bytes()

@pytest.fixture(scope="session")
def pimco_xml() -> bytes:
    """PIMCO Income Fund: placeholder CUSIPs, negative values, internal IDs."""
    return (FIXTURES / "pimco_nport.xml").read_bytes()

# Build a submissions payload in EDGAR's parallel-array shape.
def make_submissions(cik: str, forms: list[dict[str, str]]) -> dict:
    keys = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
    recent = {k: [f.get(k, "") for f in forms] for k in keys}
    return {"cik": cik, "name": "Test Filer", "filings": {"recent": recent}}

@pytest.fixture
def submissions_spy() -> dict:
    return make_submissions(
        "884394",
        [
            {
                "form": "NPORT-P",
                "accessionNumber": "0001410368-26-055357",
                "filingDate": "2026-05-28",
                "reportDate": "2026-03-31",
                "primaryDocument": "xslFormNPORT-P_X01/primary_doc.xml",
            },
            {
                "form": "NPORT-P",
                "accessionNumber": "0001410368-26-020131",
                "filingDate": "2026-02-26",
                "reportDate": "2025-12-31",
                "primaryDocument": "xslFormNPORT-P_X01/primary_doc.xml",
            },
        ],
    )

@pytest.fixture
def submissions_multi_series() -> dict:
    # Three filings sharing one date: a trust with three fund series.
    return make_submissions(
        "810893",
        [
            {
                "form": "NPORT-P",
                "accessionNumber": f"0001099263-26-00724{i}",
                "filingDate": "2026-05-29",
                "reportDate": "2026-03-31",
                "primaryDocument": "xslFormNPORT-P_X01/primary_doc.xml",
            }
            for i in range(3)
        ],
    )

@pytest.fixture
def submissions_no_nport() -> dict:
    # A valid filer with no fund filings, e.g. an operating company.
    return make_submissions(
        "320193",
        [
            {
                "form": "10-K",
                "accessionNumber": "0000320193-25-000001",
                "filingDate": "2025-11-01",
                "reportDate": "2025-09-30",
                "primaryDocument": "aapl-20250930.htm",
            }
        ],
    )
