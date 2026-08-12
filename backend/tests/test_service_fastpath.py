from pathlib import Path

import httpx
import pytest

from nport.edgar import EdgarClient
from nport.models import Filing
from nport.service import resolve
from tests.conftest import make_submissions

FIXTURES = Path(__file__).parent / "fixtures"

# A trust filing many N-PORTs on one date.
def multi_series_submissions(count: int = 94) -> dict:
    return make_submissions(
        "810893",
        [
            {
                "form": "NPORT-P",
                "accessionNumber": f"0001099263-26-{i:06d}",
                "filingDate": "2026-05-29",
                "reportDate": "2026-03-31",
                "primaryDocument": "xslFormNPORT-P_X01/primary_doc.xml",
            }
            for i in range(count)
        ],
    )

# Stub EDGAR
class Recorder:
    def __init__(self, *, submissions: dict, document: bytes,
                 series_html: bytes | None, series_atom: bytes | None):
        self.urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            self.urls.append(url)
            if "submissions" in url:
                return httpx.Response(200, json=submissions)
            if "scd=series&view=mutual-fund" in url or (
                "scd=series" in url and "output=atom" not in url
            ):
                if series_html is None:
                    return httpx.Response(503, text="unavailable")
                return httpx.Response(200, content=series_html)
            if "output=atom" in url:
                if series_atom is None:
                    return httpx.Response(503, text="unavailable")
                return httpx.Response(200, content=series_atom)
            return httpx.Response(200, content=document)

        self._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.edgar = EdgarClient(self._client)

    @property
    def document_fetches(self) -> int:
        return sum(1 for u in self.urls if "Archives" in u)

    async def aclose(self) -> None:
        await self._client.aclose()

@pytest.fixture
def pimco_doc() -> bytes:
    return (FIXTURES / "pimco_nport.xml").read_bytes()

@pytest.fixture
def series_html() -> bytes:
    return (FIXTURES / "series_index.html").read_bytes()

@pytest.fixture
def series_atom() -> bytes:
    return (FIXTURES / "series_filings.xml").read_bytes()

class TestFastPath:
    async def test_picker_costs_two_requests_not_ninety_four(
        self, pimco_doc, series_html, series_atom
    ):
        rec = Recorder(
            submissions=multi_series_submissions(94),
            document=pimco_doc,
            series_html=series_html,
            series_atom=series_atom,
        )
        result = await resolve(rec.edgar, "810893")
        await rec.aclose()

        assert isinstance(result, list)
        assert len(result) == 3  # fixture holds three series
        assert rec.document_fetches == 0, "fast path should fetch no filings"
        assert len(rec.urls) <= 3

    async def test_selecting_series_fetches_only_that_fund(
        self, pimco_doc, series_html, series_atom
    ):
        rec = Recorder(
            submissions=multi_series_submissions(94),
            document=pimco_doc,
            series_html=series_html,
            series_atom=series_atom,
        )
        result = await resolve(rec.edgar, "810893", series_id="S000016548")
        await rec.aclose()

        assert isinstance(result, Filing)
        assert result.series_name == "PIMCO Income Fund"
        assert rec.document_fetches == 1
        # No submissions lookup is needed when the series feed answers directly
        assert not any("submissions" in u for u in rec.urls)

class TestFallback:
    async def test_falls_back_when_series_index_unavailable(
        self, pimco_doc, series_atom
    ):
        rec = Recorder(
            submissions=multi_series_submissions(3),
            document=pimco_doc,
            series_html=None,  # fast path fails
            series_atom=series_atom,
        )
        result = await resolve(rec.edgar, "810893")
        await rec.aclose()

        assert isinstance(result, list)
        assert len(result) == 3
        assert rec.document_fetches == 3, "fallback reads each filing header"

    async def test_falls_back_when_markup_unrecognized(self, pimco_doc, series_atom):
        rec = Recorder(
            submissions=multi_series_submissions(3),
            document=pimco_doc,
            series_html=b"<html>redesigned page</html>",
            series_atom=series_atom,
        )
        result = await resolve(rec.edgar, "810893")
        await rec.aclose()

        assert isinstance(result, list)
        assert rec.document_fetches == 3

    async def test_series_selection_falls_back_when_atom_unavailable(
        self, pimco_doc, series_html
    ):
        rec = Recorder(
            submissions=multi_series_submissions(3),
            document=pimco_doc,
            series_html=series_html,
            series_atom=None,  # fast lookup fails
        )
        result = await resolve(rec.edgar, "810893", series_id="S000016548")
        await rec.aclose()

        assert isinstance(result, Filing)
        assert result.series_name == "PIMCO Income Fund"


class TestSingleSeriesUnaffected:
    async def test_single_filing_skips_series_lookups(
        self, submissions_spy, spy_xml, series_html, series_atom
    ):
        rec = Recorder(
            submissions=submissions_spy,
            document=spy_xml,
            series_html=series_html,
            series_atom=series_atom,
        )
        result = await resolve(rec.edgar, "884394")
        await rec.aclose()

        assert isinstance(result, Filing)
        assert not any("scd=series" in u for u in rec.urls)
        assert len(rec.urls) == 2
