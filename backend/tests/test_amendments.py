from nport.edgar import extract_nport_filings, latest_filing_group
from tests.conftest import make_submissions

def filing(form: str, accession: str, filed: str) -> dict[str, str]:
    return {
        "form": form,
        "accessionNumber": accession,
        "filingDate": filed,
        "reportDate": "2026-03-31",
        "primaryDocument": "xslFormNPORT-P_X01/primary_doc.xml",
    }

def test_amendment_filed_later_supersedes_the_original():
    subs = make_submissions(
        "884394",
        [
            filing("NPORT-P/A", "0001410368-26-060000", "2026-06-15"),
            filing("NPORT-P", "0001410368-26-055357", "2026-05-28"),
        ],
    )
    latest = latest_filing_group(extract_nport_filings(subs))
    assert len(latest) == 1
    assert latest[0].form_type == "NPORT-P/A"
    assert latest[0].accession_number == "0001410368-26-060000"

def test_original_wins_when_it_is_the_newer_filing():
    subs = make_submissions(
        "884394",
        [
            filing("NPORT-P", "0001410368-26-055357", "2026-05-28"),
            filing("NPORT-P/A", "0001410368-25-000001", "2025-11-20"),
        ],
    )
    latest = latest_filing_group(extract_nport_filings(subs))
    assert len(latest) == 1
    assert latest[0].form_type == "NPORT-P"


def test_amendment_and_original_on_one_date_are_both_returned():
    subs = make_submissions(
        "810893",
        [
            filing("NPORT-P", "0001099263-26-007248", "2026-05-29"),
            filing("NPORT-P/A", "0001099263-26-007249", "2026-05-29"),
        ],
    )
    latest = latest_filing_group(extract_nport_filings(subs))
    assert len(latest) == 2
