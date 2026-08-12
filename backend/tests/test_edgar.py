import pytest

from nport.edgar import (
    build_document_url,
    extract_nport_filings,
    latest_filing_group,
    normalize_cik,
)
from nport.errors import InvalidCik, NoNportFilings

class TestNormalizeCik:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("884394", "0000884394"),
            ("0000884394", "0000884394"),
            ("CIK0000884394", "0000884394"),
            ("cik884394", "0000884394"),
            ("  884394  ", "0000884394"),
            ("1", "0000000001"),
        ],
    )
    def test_accepts_common_forms(self, raw, expected):
        assert normalize_cik(raw) == expected

    @pytest.mark.parametrize("raw", ["", "abc", "12345678901", "88-4394", "1e5", None])
    def test_rejects_invalid(self, raw):
        with pytest.raises(InvalidCik):
            normalize_cik(raw)

class TestBuildDocumentUrl:
    def test_strips_xsl_viewer_segment(self):
        url = build_document_url(
            "0000884394", "000141036826055357", "xslFormNPORT-P_X01/primary_doc.xml"
        )
        assert "xslFormNPORT-P" not in url
        assert url.endswith("/884394/000141036826055357/primary_doc.xml")

    def test_archive_path_drops_leading_zeros(self):
        url = build_document_url("0000884394", "000141036826055357", "primary_doc.xml")
        assert "/data/884394/" in url

class TestExtractFilings:
    def test_selects_nport_only(self, submissions_spy):
        filings = extract_nport_filings(submissions_spy)
        assert len(filings) == 2
        assert all(f.form_type.startswith("NPORT-P") for f in filings)

    def test_ignores_non_fund_forms(self, submissions_no_nport):
        assert extract_nport_filings(submissions_no_nport) == []

class TestLatestFilingGroup:
    def test_raises_when_no_filings(self):
        with pytest.raises(NoNportFilings) as exc:
            latest_filing_group([])
        assert "operating company" in exc.value.message

    # A trust files one N-PORT per series on the same date.
    # Returning only the first would silently show one arbitrary fund.
    def test_returns_all_filings_sharing_newest_date(self, submissions_multi_series):
        group = latest_filing_group(extract_nport_filings(submissions_multi_series))
        assert len(group) == 3
        assert {f.filing_date for f in group} == {"2026-05-29"}
