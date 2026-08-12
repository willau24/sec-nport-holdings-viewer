import asyncio
import logging

from .edgar import (
    EdgarClient,
    build_document_url,
    extract_nport_filings,
    latest_filing_group,
    normalize_cik,
)
from .errors import NportError, SeriesNotFound
from .models import Filing, FilingRef, SeriesRef
from .parser import meaningful, parse_filing, parse_header
from .series_index import (
    build_series_refs,
    parse_latest_filing,
    parse_series_index,
    series_filings_url,
    series_index_url,
)

logger = logging.getLogger(__name__)

def _document_url(ref: FilingRef) -> str:
    return build_document_url(ref.cik, ref.accession_no_dashes, ref.primary_document)

def _series_sort_key(series: SeriesRef) -> tuple[bool, str]:
    name = series.series_name
    return (name is None, (name or "").lower())

# Return every N-PORT filing sharing the filer's most recent filing date.
async def _resolve_latest_filings(client: EdgarClient, cik: str) -> list[FilingRef]:
    normalized = normalize_cik(cik)
    submissions = await client.fetch_submissions(normalized)
    filings = extract_nport_filings(submissions)
    return latest_filing_group(filings)

# Label each filing with its fund series
async def _resolve_series_fallback(
    client: EdgarClient, filings: list[FilingRef]
) -> list[SeriesRef]:
    async def _one(ref: FilingRef) -> tuple[SeriesRef, NportError | None]:
        try:
            content = await client.fetch_document(_document_url(ref))
            header = parse_header(content)
        except NportError as exc:
            return SeriesRef(series_id=None, series_name=None, filing=ref), exc
        return (
            SeriesRef(
                series_id=meaningful(header.get("seriesId")),
                series_name=meaningful(header.get("seriesName")),
                filing=ref,
            ),
            None,
        )

    outcomes = await asyncio.gather(*(_one(ref) for ref in filings))
    
    errors = [exc for _, exc in outcomes if exc is not None]
    if errors and len(errors) == len(outcomes):
        raise errors[0]

    results = [ref for ref, _ in outcomes]
    return sorted(results, key=_series_sort_key)

# Fetch and fully parse one filing's holdings.
async def fetch_filing(client: EdgarClient, ref: FilingRef) -> Filing:
    url = _document_url(ref)
    content = await client.fetch_document(url)
    return parse_filing(
        content,
        cik=ref.cik,
        source_url=url,
        accession_number=ref.accession_number,
        filing_date=ref.filing_date,
        form_type=ref.form_type,
    )

# List a trust's funds in one request via the series index.
async def resolve_series(
    edgar: EdgarClient, cik: str, filing_date: str = ""
) -> list[SeriesRef]:
    try:
        content = await edgar.fetch_document(series_index_url(cik))
    except NportError:
        return []
    mapping = parse_series_index(content)
    if not mapping:
        return []
    return build_series_refs(mapping, cik, filing_date)

# Find one fund's most recent N-PORT filing in a single request.
async def resolve_filing_for_series(
    edgar: EdgarClient, cik: str, series_id: str
) -> tuple[FilingRef | None, bool]:
    try:
        content = await edgar.fetch_document(series_filings_url(series_id))
    except NportError:
        return None, False
    return parse_latest_filing(content, cik), True

# Resolve a CIK using an already-open client
async def resolve(
    edgar: EdgarClient, cik: str, series_id: str | None = None
) -> Filing | list[SeriesRef]:
    normalized = normalize_cik(cik)

    # A specific fund was requested
    if series_id is not None:
        ref, answered = await resolve_filing_for_series(edgar, normalized, series_id)
        if ref is not None:
            return await fetch_filing(edgar, ref)
        if answered:
            # The feed responded and listed no N-PORT filings for this fund
            raise SeriesNotFound()

    filings = await _resolve_latest_filings(edgar, normalized)

    if len(filings) == 1 and series_id is None:
        return await fetch_filing(edgar, filings[0])

    # Multi-series trust: try the one-request series index
    if series_id is None:
        fast = await resolve_series(edgar, normalized, filings[0].filing_date)
        if len(fast) > 1:
            return fast

    # Fall back to reading each filing's header for its series name
    logger.warning(
        "series index unavailable for CIK %s; falling back to %d filing fetches",
        normalized,
        len(filings),
    )
    series = await _resolve_series_fallback(edgar, filings)

    if series_id is not None:
        for candidate in series:
            if candidate.series_id == series_id:
                return await fetch_filing(edgar, candidate.filing)
        raise SeriesNotFound()

    if len(series) == 1:
        return await fetch_filing(edgar, series[0].filing)

    return series
