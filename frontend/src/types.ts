export type IdentifierType = 'cusip' | 'isin' | 'ticker' | 'other' | 'none';

export interface Holding {
  identifier: string;
  identifier_type: IdentifierType;
  identifier_desc: string | null;
  name: string;
  title: string;
  balance: string | null;
  units: string | null;
  value_usd: string | null;
  pct_val: string | null;
  currency: string | null;
}

export interface HoldingsResponse {
  requires_series_selection: false;
  cik: string;
  registrant_name: string | null;
  series_name: string | null;
  series_id: string | null;
  filing_date: string;
  period_end: string | null;
  accession_number: string;
  form_type: string;
  source_url: string;
  total_value: string;
  total_assets: string | null;
  net_assets: string | null;
  holdings_count: number;
  holdings: Holding[];
}

export interface SeriesEntry {
  series_id: string | null;
  series_name: string | null;
  accession_number: string;
  filing_date: string;
}

export interface SeriesSelectionResponse {
  requires_series_selection: true;
  cik: string;
  filing_date: string;
  series_count: number;
  series: SeriesEntry[];
}

export type FundResponse = HoldingsResponse | SeriesSelectionResponse;

export interface ApiError {
  error: string;
  detail: string;
}

export function isSeriesSelection(
  response: FundResponse,
): response is SeriesSelectionResponse {
  return response.requires_series_selection;
}
