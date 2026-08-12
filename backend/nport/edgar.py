from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from . import config
from .errors import (
    CikNotFound,
    EdgarRateLimited,
    EdgarUnavailable,
    InvalidCik,
    NoNportFilings,
)
from .models import FilingRef

_CIK_RE = re.compile(r"^\d{1,10}$")

# EDGAR's XSL-rendered HTML viewer path. The submissions JSON reports
# primaryDocument including this prefix, so we need to strip it or else
# it'll yield styled HTML.
_XSL_PREFIX_RE = re.compile(r"^xslFormNPORT-P[^/]*/")

def normalize_cik(raw: str) -> str:
    if raw is None:
        raise InvalidCik()
    cik = str(raw).strip()

    # Accept the form "CIK0000884394"
    # (it was annoying to test and not accept)
    if cik.upper().startswith("CIK"):
        cik = cik[3:]
    if not _CIK_RE.match(cik):
        raise InvalidCik()
    return cik.lstrip("0").zfill(10)

# Build the URL of a filing's raw XML document.
def build_document_url(cik: str, accession_no_dashes: str, primary_document: str) -> str:
    doc = _XSL_PREFIX_RE.sub("", primary_document.strip())
    cik_plain = cik.lstrip("0") or "0"
    return f"{config.ARCHIVES_BASE}/{cik_plain}/{accession_no_dashes}/{doc}"

class EdgarClient:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._owns_client = client is None
        self._semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)

    async def __aenter__(self) -> EdgarClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": config.USER_AGENT,
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=httpx.Timeout(
                    config.READ_TIMEOUT, connect=config.CONNECT_TIMEOUT
                ),
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, url: str) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("EdgarClient must be used as an async context manager")

        last_exc: Exception | None = None
        for attempt in range(config.MAX_RETRIES):
            try:
                async with self._semaphore:
                    response = await self._client.get(url)
            except httpx.TimeoutException as exc:
                last_exc = exc
            except httpx.HTTPError as exc:
                last_exc = exc
            else:
                if response.status_code == 404:
                    # Caller decides what to do with a 404 
                    return response
                # EDGAR signals throttling with 403 as well as 429
                if response.status_code in (403, 429):
                    raise EdgarRateLimited()
                if response.status_code >= 500:
                    last_exc = EdgarUnavailable()
                else:
                    return response

            if attempt < config.MAX_RETRIES - 1:
                await asyncio.sleep(config.RETRY_BACKOFF_BASE * (2**attempt))

        if isinstance(last_exc, (EdgarRateLimited, EdgarUnavailable)):
            raise last_exc
        raise EdgarUnavailable()

    # Fetch a filer's submissions index
    async def fetch_submissions(self, cik: str) -> dict[str, Any]:
        url = config.SUBMISSIONS_URL.format(cik=cik)
        response = await self._get(url)
        if response.status_code == 404:
            raise CikNotFound(f"No SEC filer found with CIK {cik.lstrip('0')}.")
        try:
            return response.json()
        except ValueError as exc:
            raise EdgarUnavailable(
                "SEC EDGAR returned an unreadable response."
            ) from exc
        
    # Fetch a filing document's raw bytes.
    async def fetch_document(self, url: str) -> bytes:
        response = await self._get(url)
        if response.status_code == 404:
            raise EdgarUnavailable(f"Filing document not found at {url}.")
        return response.content

# Extract all N-PORT-P filing references from a submissions payload.
# I included both NPORT-P and NPORT-P/A
def extract_nport_filings(submissions: dict[str, Any]) -> list[FilingRef]:
    cik_raw = submissions.get("cik", "")
    cik = str(cik_raw).zfill(10)

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    documents = recent.get("primaryDocument", [])

    filings: list[FilingRef] = []
    for i, form in enumerate(forms):
        if not str(form).startswith("NPORT-P"):
            continue
        if i >= len(accessions) or i >= len(filing_dates) or i >= len(documents):
            continue
        filings.append(
            FilingRef(
                cik=cik,
                accession_number=accessions[i],
                filing_date=filing_dates[i],
                report_date=report_dates[i] if i < len(report_dates) else "",
                form_type=form,
                primary_document=documents[i],
            )
        )

    # EDGAR already returns recent filings in this order, but sorting avoids depending on that
    # if they change that in the future
    filings.sort(key=lambda f: (f.filing_date, f.accession_number), reverse=True)
    return filings

# Return every filing sharing the most recent filing date
# See README for why this is necessary
def latest_filing_group(filings: list[FilingRef]) -> list[FilingRef]:
    if not filings:
        raise NoNportFilings()
    newest = filings[0].filing_date
    return [f for f in filings if f.filing_date == newest]
