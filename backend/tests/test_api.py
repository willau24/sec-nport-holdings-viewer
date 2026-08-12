from pathlib import Path

import httpx
import pytest

from nport import api
from nport.edgar import EdgarClient

FIXTURES = Path(__file__).parent / "fixtures"
SERIES_INDEX = (FIXTURES / "series_index.html").read_bytes()
SERIES_ATOM = (FIXTURES / "series_filings.xml").read_bytes()
EMPTY_ATOM = b'<?xml version="1.0"?><feed><title>Test Filer</title></feed>'

class StubEdgar:
    def __init__(self, submissions: dict, document: bytes, *,
                 subs_status: int = 200, doc_status: int = 200):
        self.requests: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            self.requests.append(url)
            if "submissions" in url:
                if subs_status != 200:
                    return httpx.Response(subs_status, text="error")
                return httpx.Response(200, json=submissions)
            if doc_status != 200:
                return httpx.Response(doc_status, text="error")

            if "output=atom" in url:
                if "S000016548" in url:
                    return httpx.Response(200, content=SERIES_ATOM)
                return httpx.Response(200, content=EMPTY_ATOM)
            if "scd=series" in url:
                return httpx.Response(200, content=SERIES_INDEX)
            # The XSL viewer path must never be requested because it serves HTML
            assert "xslFormNPORT-P" not in url, f"requested XSL viewer: {url}"
            return httpx.Response(200, content=document)

        self._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.edgar = EdgarClient(self._client)

    async def aclose(self) -> None:
        await self._client.aclose()

# Issue a request with the app's EDGAR client replaced by the stub
async def call(stub: StubEdgar, path: str) -> httpx.Response:
    api.app.state.edgar = stub.edgar
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        return await client.get(path)

def build_app(submissions: dict, document: bytes, *, doc_status: int = 200,
              subs_status: int = 200) -> StubEdgar:
    return StubEdgar(
        submissions, document, subs_status=subs_status, doc_status=doc_status
    )

@pytest.fixture(autouse=True)
def _clear_cache():
    api._cache.clear()
    yield
    api._cache.clear()

class TestHoldingsEndpoint:
    async def test_returns_holdings(self, submissions_spy, spy_xml):
        app = build_app(submissions_spy, spy_xml)
        response = await call(app, "/api/funds/884394/holdings")
        assert response.status_code == 200
        body = response.json()
        assert body["requires_series_selection"] is False
        assert body["holdings_count"] == 8
        assert body["period_end"] == "2026-03-31"

    # Large totals would lose precision if not sent as strings
    async def test_decimals_serialized_as_strings(self, submissions_spy, spy_xml):
        app = build_app(submissions_spy, spy_xml)
        body = (await call(app, "/api/funds/884394/holdings")).json()
        assert isinstance(body["total_value"], str)
        assert isinstance(body["holdings"][0]["value_usd"], str)
        assert "E" not in body["total_value"].upper()

    async def test_identifier_types_exposed(self, submissions_spy, spy_xml):
        app = build_app(submissions_spy, spy_xml)
        body = (await call(app, "/api/funds/884394/holdings")).json()
        types = {h["identifier_type"] for h in body["holdings"]}
        assert types == {"cusip", "isin"}
        assert all(h["identifier"] != "000000000" for h in body["holdings"])

    async def test_cik_forms_are_equivalent(self, submissions_spy, spy_xml):
        app = build_app(submissions_spy, spy_xml)
        a = (await call(app, "/api/funds/884394/holdings")).json()
        b = (await call(app, "/api/funds/CIK0000884394/holdings")).json()
        assert a["accession_number"] == b["accession_number"]

class TestSeriesSelection:
    # Three filings share a date, so the API must not guess a fund.
    async def test_multi_series_returns_picker(self, submissions_multi_series, pimco_xml):
        app = build_app(submissions_multi_series, pimco_xml)
        response = await call(app, "/api/funds/810893/holdings")
        assert response.status_code == 200
        body = response.json()
        assert body["requires_series_selection"] is True
        assert body["series_count"] == 3

    async def test_selecting_series_returns_holdings(
        self, submissions_multi_series, pimco_xml
    ):
        app = build_app(submissions_multi_series, pimco_xml)
        body = (
            await call(app, "/api/funds/810893/holdings?series=S000016548")
        ).json()
        assert body["requires_series_selection"] is False
        assert body["series_name"] == "PIMCO Income Fund"

    # A registered fund with no filing is a miss or bad
    # request: the user picked it from a list we supplied.
    async def test_unfiled_series_is_404(self, submissions_multi_series, pimco_xml):
        app = build_app(submissions_multi_series, pimco_xml)
        response = await call(app, "/api/funds/810893/holdings?series=S000000000")
        assert response.status_code == 404
        assert "no N-PORT filings available" in response.json()["detail"]

class TestErrorTaxonomy:
    async def test_invalid_cik_is_400(self, submissions_spy, spy_xml):
        app = build_app(submissions_spy, spy_xml)
        response = await call(app, "/api/funds/notacik/holdings")
        assert response.status_code == 400
        assert "1-10 digits" in response.json()["detail"]

    async def test_unknown_cik_is_404(self, submissions_spy, spy_xml):
        app = build_app(submissions_spy, spy_xml, subs_status=404)
        response = await call(app, "/api/funds/9999999999/holdings")
        assert response.status_code == 404
        assert "No SEC filer" in response.json()["detail"]

    async def test_operating_company_gets_specific_message(
        self, submissions_no_nport, spy_xml
    ):
        app = build_app(submissions_no_nport, spy_xml)
        response = await call(app, "/api/funds/320193/holdings")
        assert response.status_code == 404
        assert "operating company" in response.json()["detail"]

    async def test_rate_limit_is_429(self, submissions_spy, spy_xml):
        app = build_app(submissions_spy, spy_xml, subs_status=429)
        response = await call(app, "/api/funds/884394/holdings")
        assert response.status_code == 429

    async def test_edgar_outage_is_502(self, submissions_spy, spy_xml):
        app = build_app(submissions_spy, spy_xml, subs_status=503)
        response = await call(app, "/api/funds/884394/holdings")
        assert response.status_code == 502

class TestCaching:
    async def test_second_request_does_not_refetch(self, submissions_spy, spy_xml):
        stub = build_app(submissions_spy, spy_xml)
        await call(stub, "/api/funds/884394/holdings")
        after_first = len(stub.requests)
        assert after_first > 0

        await call(stub, "/api/funds/884394/holdings")
        assert len(stub.requests) == after_first

    async def test_cache_key_distinguishes_series(
        self, submissions_multi_series, pimco_xml
    ):
        stub = build_app(submissions_multi_series, pimco_xml)
        picker = (await call(stub, "/api/funds/810893/holdings")).json()
        assert picker["requires_series_selection"] is True

        selected = (
            await call(stub, "/api/funds/810893/holdings?series=S000016548")
        ).json()
        assert selected["requires_series_selection"] is False

