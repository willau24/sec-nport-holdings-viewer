import { useMemo, useState } from 'react';
import type { SeriesSelectionResponse } from './types';

interface Props {
  data: SeriesSelectionResponse;
  onSelect: (seriesId: string) => void;
}

export function SeriesPicker({ data, onSelect }: Props) {
  const [filter, setFilter] = useState('');

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return data.series;
    return data.series.filter((s) =>
      (s.series_name ?? s.accession_number).toLowerCase().includes(needle),
    );
  }, [data.series, filter]);

  return (
    <section className="panel">
      <h2>Select a fund</h2>
      <p className="hint">
        CIK {data.cik.replace(/^0+/, '')} is a trust containing{' '}
        {data.series_count.toLocaleString()} funds. Choose one to view its
        holdings.
      </p>

      <input
        type="search"
        className="filter-input"
        placeholder="Filter funds…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        aria-label="Filter funds"
      />

      <ul className="series-list">
        {visible.map((s) => {
          const id = s.series_id;
          return (
            <li key={id ?? s.accession_number}>
              <button
                type="button"
                className="series-button"
                disabled={!id}
                onClick={() => id && onSelect(id)}
                title={!id ? 'This filing has no series identifier' : undefined}
              >
                <span className="series-name">
                  {s.series_name ?? `Filing ${s.accession_number}`}
                </span>
                {id && <span className="series-id mono">{id}</span>}
              </button>
            </li>
          );
        })}
      </ul>

      {visible.length === 0 && <p className="empty">No funds match “{filter}”.</p>}
    </section>
  );
}
