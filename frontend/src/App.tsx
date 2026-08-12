import { useCallback, useRef, useState } from 'react';
import { fetchHoldings, HoldingsError } from './api';
import { HoldingsTable } from './HoldingsTable';
import { SeriesPicker } from './SeriesPicker';
import { formatCurrency, formatDate } from './format';
import { isSeriesSelection, type FundResponse } from './types';
import './App.css';

const EXAMPLES = [
  { cik: '884394', label: 'SPDR S&P 500 ETF' },
  { cik: '810893', label: 'PIMCO Funds (multi-fund trust)' },
];

export default function App() {
  const [cik, setCik] = useState('');
  const [data, setData] = useState<FundResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const activeCik = useRef('');
  const inflight = useRef<AbortController | null>(null);

  const load = useCallback(async (targetCik: string, seriesId?: string) => {
    const trimmed = targetCik.trim();
    if (!trimmed) return;

    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;

    activeCik.current = trimmed;
    setLoading(true);
    setError(null);
    if (!seriesId) setData(null);

    try {
      const result = await fetchHoldings(trimmed, seriesId, controller.signal);
      if (controller.signal.aborted) return;
      setData(result);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setError(
        err instanceof HoldingsError
          ? err.message
          : 'Something went wrong. Please try again.',
      );
      setData(null);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void load(cik);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>SEC N-PORT Holdings Viewer</h1>
        <p className="subtitle">
          Enter a fund's Central Index Key to view holdings from its most recent
          Form N-PORT filing.
        </p>
      </header>

      <form className="search" onSubmit={onSubmit}>
        <input
          type="text"
          inputMode="numeric"
          className="cik-input"
          placeholder="e.g. 884394"
          value={cik}
          onChange={(e) => setCik(e.target.value)}
          aria-label="Central Index Key"
        />
        <button type="submit" className="primary" disabled={loading || !cik.trim()}>
          {loading ? 'Loading…' : 'View holdings'}
        </button>
      </form>

      <div className="examples">
        Try:{' '}
        {EXAMPLES.map((ex, i) => (
          <span key={ex.cik}>
            {i > 0 && ' · '}
            <button
              type="button"
              className="link"
              onClick={() => {
                setCik(ex.cik);
                void load(ex.cik);
              }}
            >
              {ex.label}
            </button>
          </span>
        ))}
      </div>

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {loading && (
        <p className="loading">
          Fetching from SEC EDGAR… large funds can take a few seconds.
        </p>
      )}

      {!loading && data && isSeriesSelection(data) && (
        <SeriesPicker
          data={data}
          onSelect={(seriesId) => void load(activeCik.current, seriesId)}
        />
      )}

      {!loading && data && !isSeriesSelection(data) && (
        <section className="panel">
          <div className="filing-meta">
            <h2>{data.series_name ?? data.registrant_name ?? 'Fund'}</h2>
            {data.series_name && data.registrant_name && (
              <p className="hint">{data.registrant_name}</p>
            )}
            <dl className="meta-grid">
              <div>
                <dt>Period end</dt>
                <dd>{formatDate(data.period_end)}</dd>
              </div>
              <div>
                <dt>Filed</dt>
                <dd>{formatDate(data.filing_date)}</dd>
              </div>
              <div>
                <dt>Holdings</dt>
                <dd>{data.holdings_count.toLocaleString()}</dd>
              </div>
              <div>
                <dt>Total value</dt>
                <dd>{formatCurrency(data.total_value)}</dd>
              </div>
            </dl>
            <a
              className="source-link"
              href={data.source_url}
              target="_blank"
              rel="noreferrer"
            >
              View filing on sec.gov ({data.form_type} {data.accession_number})
            </a>
          </div>

          <HoldingsTable holdings={data.holdings} />
        </section>
      )}
    </div>
  );
}
