# SEC N-PORT Holdings Viewer

Author: Will McCormick — willster2424@gmail.com

Enter a fund's Central Index Key (CIK) to view the portfolio holdings from its
most recent SEC Form N-PORT filing. A FastAPI backend fetches and parses the
filing from EDGAR; a React SPA displays the holdings with sorting and filtering.

**Live at https://sec-nport-holdings-viewer-production.up.railway.app**

Try CIK `884394` (SPDR S&P 500 ETF) or `810893` (PIMCO Funds, a multi-fund trust).

## Build

```bash
docker build -t nport-viewer .
```

## Run

```bash
docker run -p 8000:8000 nport-viewer
```

Open http://localhost:8000

To run without Docker, see `backend/README` and `frontend/README.md`.

## Test

```bash
cd backend && ./.venv/bin/python -m pytest    # 79 tests
cd frontend && npm test                        # 21 tests
```

Tests run fully offline against saved EDGAR responses. They are not part of the
Docker build.

## Requirements met

Core: CIK lookup, and for each holding the CUSIP, title/name, balance, and value.

Optional enhancements completed:

- **Error handling** — a typed error listing; each case returns its own HTTP
  status and a message the UI displays directly.
- **Enhanced UI/UX** — sortable columns, text filter, virtualized table for
  filings with ~11,000 holdings.
- **Caching** — in-memory TTL + LRU cache with single-flight loading.
- **Testing** — 100 tests across both halves of the stack.
- **Containerization** — multi-stage Dockerfile; one image serves API and SPA.

## Core decisions

### A CIK identifies a filer, not a fund

A CIK often belongs to a fund *trust* containing many funds, each filing its own
N-PORT on the same date — PIMCO Funds (CIK 810893) files ~94. "The most recent
filing" therefore has no single answer, and picking one would silently show an
arbitrary fund. The backend returns the list of funds rather than guessing; the
frontend shows a picker and keeps it in state.

### Fast-path series lookup

Naming each fund in a trust by opening its filing costs ~94 requests. Instead one
request to EDGAR's series index returns every fund name, and one more resolves the
selected fund's id — ~2 requests instead of ~94, falling back to the
per-filing method if the scrape fails.

### Identifier fallback

Holdings without a CUSIP carry the placeholder `000000000`; the real identifier is
an ISIN or internal ID stored as an XML *attribute* under `<identifiers>`. For example, 27 of
SPY's 503 holdings need this, as do 1,580 of PIMCO Income Fund's 10,796.
