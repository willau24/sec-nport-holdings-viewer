# N-PORT Viewer — Backend

FastAPI service that resolves a CIK to its most recent Form N-PORT filing on SEC
EDGAR, parses the portfolio holdings from the filing XML, and serves them as
JSON. In production it also serves the React frontend.

## Build

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
```

## Run

```bash
./.venv/bin/uvicorn nport.api:app --port 8000
```

`GET /api/funds/{cik}/holdings` — holdings, or the fund list for a multi-fund
trust. Add `?series=<seriesId>` to select one fund. `GET /api/health` for status.

## Test

```bash
./.venv/bin/python -m pytest
```

79 tests, run offline against saved EDGAR responses in `tests/fixtures`.

## Decisions

### Caching

Responses are cached in memory for one hour, keyed by `(cik, series_id)` and
normalized so `884394` and `CIK0000884394` share an entry. N-PORT filings are
monthly and immutable once filed, so staleness risk is minimal. The cache is
bounded by an LRU limit because a single cached filing can hold ~11,000 holdings.
Concurrent misses on one key share a single load, which matters because a cold
lookup for a large trust can cost many upstream requests at once.
