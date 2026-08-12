import { describe, expect, it } from 'vitest';
import {
  formatCurrency,
  formatDate,
  formatPercent,
  formatQuantity,
  formatUnits,
  isNegative,
  toNumber,
} from '../src/format';

describe('toNumber', () => {
  it('parses decimal strings', () => {
    expect(toNumber('5426878.00000000')).toBe(5426878);
  });

  it('returns null for absent values', () => {
    expect(toNumber(null)).toBeNull();
    expect(toNumber('')).toBeNull();
  });

  it('preserves negative values', () => {
    expect(toNumber('-450975.03')).toBe(-450975.03);
  });
});

describe('formatPercent', () => {
  it('does not scale by 100', () => {
    expect(formatPercent('0.091374079743')).toBe('0.09%');
  });

  it('formats a large position without inflating it', () => {
    expect(formatPercent('9.42')).toBe('9.42%');
  });

  it('renders missing values as a dash', () => {
    expect(formatPercent(null)).toBe('—');
  });
});

describe('formatCurrency', () => {
  it('formats USD without cents', () => {
    expect(formatCurrency('595382785.38')).toBe('$595,382,785');
  });

  it('formats negative values', () => {
    expect(formatCurrency('-450975.03')).toBe('-$450,975');
  });

  it('renders missing values as a dash', () => {
    expect(formatCurrency(null)).toBe('—');
  });

  it('keeps large portfolio totals intact', () => {
    expect(formatCurrency('651284934544.53')).toBe('$651,284,934,545');
  });
});

describe('formatQuantity', () => {
  it('groups thousands', () => {
    expect(formatQuantity('5426878.00000000')).toBe('5,426,878');
  });

  it('renders missing values as a dash', () => {
    expect(formatQuantity(null)).toBe('—');
  });
});

describe('isNegative', () => {
  it('detects short and derivative positions', () => {
    expect(isNegative('-6689.36')).toBe(true);
  });

  it('is false for positive and missing values', () => {
    expect(isNegative('132.67')).toBe(false);
    expect(isNegative(null)).toBe(false);
  });
});

describe('formatUnits', () => {
  it('expands N-PORT unit codes', () => {
    expect(formatUnits('NS')).toBe('shares');
    expect(formatUnits('NC')).toBe('contracts');
    expect(formatUnits('PA')).toBe('principal');
  });

  it('uses the singular for a quantity of exactly one', () => {
    expect(formatUnits('NC', '1.000000')).toBe('contract');
    expect(formatUnits('NS', '1.00000000')).toBe('share');
  });

  it('passes through unknown codes rather than hiding them', () => {
    expect(formatUnits('XX')).toBe('XX');
  });

  it('returns empty for absent units', () => {
    expect(formatUnits(null)).toBe('');
  });
});

describe('formatDate', () => {
  it('formats filing dates', () => {
    expect(formatDate('2026-03-31')).toBe('Mar 31, 2026');
  });

  it('returns the raw value when unparseable', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });

  it('renders missing dates as a dash', () => {
    expect(formatDate(null)).toBe('—');
  });
});
