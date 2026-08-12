import { useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Holding } from './types';
import {
  formatCurrency,
  formatPercent,
  formatQuantity,
  formatUnits,
  isNegative,
  toNumber,
} from './format';

type SortKey = 'identifier' | 'name' | 'balance' | 'value_usd' | 'pct_val';
type SortDir = 'asc' | 'desc';

interface Props {
  holdings: Holding[];
}

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: 'identifier', label: 'Identifier', numeric: false },
  { key: 'name', label: 'Name', numeric: false },
  { key: 'balance', label: 'Balance', numeric: true },
  { key: 'value_usd', label: 'Value (USD)', numeric: true },
  { key: 'pct_val', label: '% of Portfolio', numeric: true },
];

const ROW_HEIGHT = 40;

export function HoldingsTable({ holdings }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('value_usd');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [filter, setFilter] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const filtered = needle
      ? holdings.filter(
          (h) =>
            h.name.toLowerCase().includes(needle) ||
            h.title.toLowerCase().includes(needle) ||
            h.identifier.toLowerCase().includes(needle),
        )
      : holdings;

    const numeric = COLUMNS.find((c) => c.key === sortKey)?.numeric ?? false;
    const direction = sortDir === 'asc' ? 1 : -1;

    // Copy before sorting
    return [...filtered].sort((a, b) => {
      if (numeric) {
        const av = toNumber(a[sortKey] as string | null);
        const bv = toNumber(b[sortKey] as string | null);
        if (av === null && bv === null) return 0;
        if (av === null) return 1;
        if (bv === null) return -1;
        return (av - bv) * direction;
      }
      return String(a[sortKey] ?? '').localeCompare(String(b[sortKey] ?? '')) * direction;
    });
  }, [holdings, filter, sortKey, sortDir]);

  // Filings may reach ~11,000 holdings - rendering every row doesn't look great.
  const virtualizer = useVirtualizer({
    count: visible.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  });

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(COLUMNS.find((c) => c.key === key)?.numeric ? 'desc' : 'asc');
    }
  }

  const items = virtualizer.getVirtualItems();

  return (
    <div className="holdings">
      <div className="holdings-toolbar">
        <input
          type="search"
          className="filter-input"
          placeholder="Filter by name or identifier…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter holdings"
        />
        <span className="holdings-count">
          {visible.length.toLocaleString()}
          {visible.length !== holdings.length && ` of ${holdings.length.toLocaleString()}`}
          {' holdings'}
        </span>
      </div>

      <div className="table-head" role="row">
        {COLUMNS.map((col) => (
          <button
            key={col.key}
            type="button"
            className={`th th-${col.key}${col.numeric ? ' numeric' : ''}`}
            onClick={() => toggleSort(col.key)}
            aria-sort={
              sortKey === col.key
                ? sortDir === 'asc'
                  ? 'ascending'
                  : 'descending'
                : 'none'
            }
          >
            {col.label}
            <span className="sort-arrow">
              {sortKey === col.key ? (sortDir === 'asc' ? '▲' : '▼') : ''}
            </span>
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="empty">No holdings match “{filter}”.</p>
      ) : (
        <div className="table-body" ref={scrollRef}>
          <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
            {items.map((item) => {
              const h = visible[item.index];
              return (
                <div
                  key={item.key}
                  className="tr"
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: item.size,
                    transform: `translateY(${item.start}px)`,
                  }}
                >
                  <div className="td td-identifier">
                    <span className="mono">{h.identifier}</span>
                    {h.identifier_type !== 'cusip' && (
                      <span
                        className="badge"
                        title={h.identifier_desc ?? h.identifier_type}
                      >
                        {h.identifier_type === 'none'
                          ? 'n/a'
                          : h.identifier_type.toUpperCase()}
                      </span>
                    )}
                  </div>
                  <div className="td td-name" title={h.title}>
                    {h.name}
                  </div>
                  <div className="td td-balance numeric">
                    {formatQuantity(h.balance)}
                    <span className="units">{formatUnits(h.units)}</span>
                  </div>
                  <div
                    className={`td td-value_usd numeric${
                      isNegative(h.value_usd) ? ' negative' : ''
                    }`}
                  >
                    {formatCurrency(h.value_usd)}
                  </div>
                  <div className="td td-pct_val numeric">
                    {formatPercent(h.pct_val)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
