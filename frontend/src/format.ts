const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

const quantity = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 2,
});

const percent = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function toNumber(value: string | null): number | null {
  if (value === null || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function formatCurrency(value: string | null): string {
  const n = toNumber(value);
  return n === null ? '—' : currency.format(n);
}

export function formatQuantity(value: string | null): string {
  const n = toNumber(value);
  return n === null ? '—' : quantity.format(n);
}

export function formatPercent(value: string | null): string {
  const n = toNumber(value);
  return n === null ? '—' : `${percent.format(n)}%`;
}

export function isNegative(value: string | null): boolean {
  const n = toNumber(value);
  return n !== null && n < 0;
}

/** Units codes used in N-PORT filings. */
const UNIT_LABELS: Record<string, string> = {
  NS: 'shares',
  NC: 'contracts',
  PA: 'principal',
  OU: 'other',
};

export function formatUnits(units: string | null): string {
  if (!units) return '';
  return UNIT_LABELS[units] ?? units;
}

export function formatDate(value: string | null): string {
  if (!value) return '—';
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}
