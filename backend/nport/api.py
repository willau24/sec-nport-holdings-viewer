import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path as FilePath
from typing import AsyncIterator, Union

from fastapi import FastAPI, Path, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .cache import FILING_TTL, TTLCache
from .edgar import EdgarClient, normalize_cik
from .errors import NportError, SeriesNotFound
from .series_index import is_valid_series_id
from .models import Filing
from .schemas import (
    ErrorResponse,
    HoldingsResponse,
    SeriesOut,
    SeriesSelectionResponse,
)
from .service import resolve

logger = logging.getLogger(__name__)

_cache: TTLCache[Union[HoldingsResponse, SeriesSelectionResponse]] = TTLCache(
    ttl=FILING_TTL
)

# Have one client for the entire process. This keeps the connection pool
# and rate limit global, so concurrent requests don't exceed the SEC limit
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with EdgarClient() as edgar:
        app.state.edgar = edgar
        yield

app = FastAPI(
    title="SEC N-PORT Holdings Viewer",
    description="Retrieve fund portfolio holdings from the most recent Form N-PORT filing.",
    version="0.1.0",
    lifespan=lifespan,
)

# Add compression to speed up fetching data
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Render pipeline errors with their message and status.
@app.exception_handler(NportError)
async def _nport_error_handler(request: Request, exc: NportError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content=ErrorResponse(
            error=type(exc).__name__, detail=exc.message
        ).model_dump(),
    )

@app.get("/api/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "cached_entries": _cache.size}

# Return holdings from a fund's most recent N-PORT filing
@app.get(
    "/api/funds/{cik}/holdings",
    response_model=Union[HoldingsResponse, SeriesSelectionResponse],
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def get_fund_holdings(
    request: Request,
    cik: str = Path(description="Central Index Key, 1-10 digits"),
    series: str | None = Query(
        default=None, description="Series ID, required for multi-series trusts"
    ),
) -> Union[HoldingsResponse, SeriesSelectionResponse]:
    # Normalize before caching so "884394" and "CIK0000884394" are the same
    normalized = normalize_cik(cik)
    if series is not None and not is_valid_series_id(series):
        raise SeriesNotFound()
    key = (normalized, series)

    async def _load() -> Union[HoldingsResponse, SeriesSelectionResponse]:
        result = await resolve(request.app.state.edgar, normalized, series)
        if isinstance(result, Filing):
            return HoldingsResponse.from_filing(result)
        return SeriesSelectionResponse(
            cik=normalized,
            filing_date=result[0].filing.filing_date if result else "",
            series_count=len(result),
            series=[SeriesOut.from_series(s) for s in result],
        )

    return await _cache.get_or_load(key, _load)

# Serve the built React frontend when present
def _mount_frontend() -> None:
    dist = FilePath(
        os.environ.get(
            "FRONTEND_DIST",
            FilePath(__file__).resolve().parents[2] / "frontend" / "dist",
        )
    )
    if not (dist / "index.html").is_file():
        logger.info("No frontend build at %s; running API only.", dist)
        return
    
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    logger.info("Serving frontend from %s", dist)

_mount_frontend()
