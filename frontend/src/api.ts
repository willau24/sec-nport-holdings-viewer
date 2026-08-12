import type { ApiError, FundResponse } from './types';

const BASE = '';

export class HoldingsError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'HoldingsError';
    this.status = status;
  }
}

// Fetch a fund's holdings, or the series list when the CIK is a list of funds
export async function fetchHoldings(
  cik: string,
  seriesId?: string,
  signal?: AbortSignal,
): Promise<FundResponse> {
  const query = seriesId ? `?series=${encodeURIComponent(seriesId)}` : '';
  const url = `${BASE}/api/funds/${encodeURIComponent(cik.trim())}/holdings${query}`;

  let response: Response;
  try {
    response = await fetch(url, { signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new HoldingsError(
      'Could not reach the server.',
      0,
    );
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = (await response.json()) as ApiError;
      if (body?.detail) detail = body.detail;
    } catch {
      // Non-JSON error body; keep generic message
    }
    throw new HoldingsError(detail, response.status);
  }

  return (await response.json()) as FundResponse;
}
