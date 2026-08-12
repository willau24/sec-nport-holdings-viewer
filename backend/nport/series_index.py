import html
import re

from .models import FilingRef, SeriesRef

BROWSE_BASE = "https://www.sec.gov/cgi-bin/browse-edgar"

# Series rows link to the series' own page. The anchor text is the fund name
_SERIES_ROW_RE = re.compile(
    r'CIK=(S\d{9})&amp;scd=series[^>]*>([^<]+)</a>', re.IGNORECASE
)

_ACCESSION_RE = re.compile(r"<accession-n[uo]mber>([^<]+)</accession-n[uo]mber>")
_FILING_DATE_RE = re.compile(r"<filing-date>([^<]+)</filing-date>")
_FILING_TYPE_RE = re.compile(r"<filing-type>([^<]+)</filing-type>")
_ENTRY_RE = re.compile(r"<entry>(.*?)</entry>", re.DOTALL)

# URL listing every fund series under a filer.
def series_index_url(cik: str) -> str:
    return (
        f"{BROWSE_BASE}?action=getcompany&CIK={cik}"
        "&scd=series&view=mutual-fund&count=500"
    )

# URL listing one series' N-PORT filings as an Atom feed
_SERIES_ID_RE = re.compile(r"^S\d{9}$")

# EDGAR series IDs are the letter S followed by nine digits.
def is_valid_series_id(series_id: str) -> bool:
    return bool(_SERIES_ID_RE.match(series_id.strip()))

def series_filings_url(series_id: str) -> str:
    return (
        f"{BROWSE_BASE}?action=getcompany&CIK={series_id}"
        "&type=NPORT-P&dateb=&owner=include&count=10&scd=filings&output=atom"
    )

# Map series ID to fund name from the series listing page.
def parse_series_index(content: bytes) -> dict[str, str]:
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        return {}

    mapping: dict[str, str] = {}
    for series_id, name in _SERIES_ROW_RE.findall(text):
        cleaned = html.unescape(name).strip()
        if cleaned and series_id not in mapping:
            mapping[series_id] = cleaned
    return mapping

# Extract the most recent N-PORT filing from a series' Atom feed.
def parse_latest_filing(content: bytes, cik: str) -> FilingRef | None:
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        return None

    for entry in _ENTRY_RE.findall(text):
        form = _first(_FILING_TYPE_RE, entry)
        if not form or not form.startswith("NPORT-P"):
            continue
        accession = _first(_ACCESSION_RE, entry)
        filing_date = _first(_FILING_DATE_RE, entry)
        if not accession or not filing_date:
            continue
        return FilingRef(
            cik=cik,
            accession_number=accession,
            filing_date=filing_date,
            report_date="",
            form_type=form,
            # browse-edgar does not name the document; N-PORT filings use this
            # filename consistently, and the fan-out fallback covers the rest.
            primary_document="primary_doc.xml",
        )
    return None


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None

def build_series_refs(
    mapping: dict[str, str], cik: str, filing_date: str = ""
) -> list[SeriesRef]:
    refs = [
        SeriesRef(
            series_id=series_id,
            series_name=name,
            filing=FilingRef(
                cik=cik,
                accession_number="",
                filing_date=filing_date,
                report_date="",
                form_type="NPORT-P",
                primary_document="primary_doc.xml",
            ),
        )
        for series_id, name in mapping.items()
    ]
    return sorted(refs, key=lambda s: (s.series_name or "").lower())
