from pathlib import Path

import pytest

from nport.series_index import (
    build_series_refs,
    parse_latest_filing,
    parse_series_index,
)

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture(scope="session")
def series_html() -> bytes:
    return (FIXTURES / "series_index.html").read_bytes()

@pytest.fixture(scope="session")
def series_atom() -> bytes:
    return (FIXTURES / "series_filings.xml").read_bytes()

class TestParseSeriesIndex:
    def test_extracts_series_names(self, series_html):
        mapping = parse_series_index(series_html)
        assert mapping.get("S000016548") == "PIMCO Income Fund"

    def test_unescapes_html_entities(self):
        raw = (
            b'<a href="?CIK=S000000001&amp;scd=series&amp;view=mutual-fund">'
            b"Fund A &amp; B</a>"
        )
        assert parse_series_index(raw)["S000000001"] == "Fund A & B"

    def test_unrecognized_markup_returns_empty(self):
        assert parse_series_index(b"<html><body>redesigned</body></html>") == {}

    def test_garbage_input_does_not_raise(self):
        assert parse_series_index(b"\x00\xff not html") == {}

class TestParseLatestFiling:
    def test_extracts_accession(self, series_atom):
        ref = parse_latest_filing(series_atom, "0000810893")
        assert ref is not None
        assert ref.accession_number == "0001099263-26-007248"

    def test_newest_entry_wins(self, series_atom):
        ref = parse_latest_filing(series_atom, "0000810893")
        assert ref.filing_date == "2026-05-29"

    def test_accession_no_dashes_matches_archive_path(self, series_atom):
        ref = parse_latest_filing(series_atom, "0000810893")
        assert ref.accession_no_dashes == "000109926326007248"

    def test_empty_feed_returns_none(self):
        assert parse_latest_filing(b"<feed></feed>", "1") is None

    def test_ignores_non_nport_entries(self):
        feed = (
            b"<feed><entry><filing-type>10-K</filing-type>"
            b"<accession-number>0000000000-00-000000</accession-number>"
            b"<filing-date>2026-01-01</filing-date></entry></feed>"
        )
        assert parse_latest_filing(feed, "1") is None

class TestBuildSeriesRefs:
    def test_sorted_by_name(self):
        refs = build_series_refs(
            {"S1": "Zebra Fund", "S2": "Alpha Fund"}, "0000810893"
        )
        assert [r.series_name for r in refs] == ["Alpha Fund", "Zebra Fund"]
