from decimal import Decimal, InvalidOperation
from io import BytesIO

from lxml import etree

from .config import NPORT_NS
from .errors import FilingParseError, UnrecognizedFiling
from .models import Filing, Holding, IdentifierType

_HOLDING_TAG = f"{{{NPORT_NS}}}invstOrSec"
_IDENTIFIERS_TAG = f"{{{NPORT_NS}}}identifiers"

# Values used in place of a real CUSIP for elements that lack one.
_PLACEHOLDER_IDS = {"", "0", "000000000", "N/A", "NA", "NONE", "NULL"}

_HEADER_FIELDS = (
    "seriesName",
    "seriesId",
    "regName",
    "repPdEnd",
    "repPdDate",
    "totAssets",
    "netAssets",
)

def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]

def _text(element: etree._Element, tag: str) -> str | None:
    child = element.find(f"{{{NPORT_NS}}}{tag}")
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None

def _decimal(element: etree._Element, tag: str) -> Decimal | None:
    raw = _text(element, tag)
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None

# Single-series funds seem to report seriesName or seriesId as "N/A"
def meaningful(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.upper() in {"N/A", "NA", "NONE"}:
        return None
    return stripped


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().upper()
    if normalized in _PLACEHOLDER_IDS:
        return True
    return set(normalized) == {"0"}

# Resolve a holding's best available identifier.
# CUSIP -> ISIN -> ticker -> other
def _resolve_identifier(
    element: etree._Element,
) -> tuple[str, IdentifierType, str | None]:
    cusip = _text(element, "cusip")
    if not _is_placeholder(cusip):
        return cusip, IdentifierType.CUSIP, None

    identifiers = element.find(_IDENTIFIERS_TAG)
    if identifiers is not None:
        preferred = {
            "isin": IdentifierType.ISIN,
            "ticker": IdentifierType.TICKER,
        }
        fallback: tuple[str, IdentifierType, str | None] | None = None
        for child in identifiers:
            name = _local(child.tag)
            value = (child.get("value") or "").strip()
            if _is_placeholder(value):
                continue
            if name in preferred:
                return value, preferred[name], None
            if name == "other" and fallback is None:
                fallback = (value, IdentifierType.OTHER, child.get("otherDesc"))
        if fallback is not None:
            return fallback

    return "N/A", IdentifierType.NONE, None


def _parse_holding(element: etree._Element) -> Holding:
    identifier, id_type, id_desc = _resolve_identifier(element)

    name = _text(element, "name")
    title = _text(element, "title")
    
    if name in (None, "N/A"):
        name = title if title not in (None, "N/A") else None
    if name is None:
        name = identifier if id_type is not IdentifierType.NONE else "—"

    return Holding(
        identifier=identifier,
        identifier_type=id_type,
        identifier_desc=id_desc,
        name=name,
        title=title or name,
        balance=_decimal(element, "balance"),
        units=_text(element, "units"),
        value_usd=_decimal(element, "valUSD"),
        pct_val=_decimal(element, "pctVal"),
        currency=_text(element, "curCd"),
    )

# Extract fund-level header fields, stopping at the first holding (resolve_series - fallback case)
def parse_header(content: bytes) -> dict[str, str]:
    header: dict[str, str] = {}
    fields = set(_HEADER_FIELDS)
    try:
        context = etree.iterparse(
            BytesIO(content), events=("end",), recover=True, huge_tree=True
        )
        for _, element in context:
            if element.tag == _HOLDING_TAG:
                # Holdings begin after the header - nothing more to collect.
                break
            tag = _local(element.tag)
            if tag in fields and element.text and tag not in header:
                header[tag] = element.text.strip()
            if len(header) == len(fields):
                break
    except etree.XMLSyntaxError as exc:
        raise FilingParseError() from exc
    return header

# Parse a complete N-PORT document into a Filing with holdings
def parse_filing(content: bytes, cik: str, source_url: str, *,
                 accession_number: str, filing_date: str,
                 form_type: str) -> Filing:
    header: dict[str, str] = {}
    holdings: list[Holding] = []
    fields = set(_HEADER_FIELDS)

    try:
        context = etree.iterparse(
            BytesIO(content), events=("end",), recover=True, huge_tree=True
        )
        for _, element in context:
            if element.tag == _HOLDING_TAG:
                holdings.append(_parse_holding(element))
                # Release the parsed subtree
                element.clear()
                parent = element.getparent()
                if parent is not None:
                    while element.getprevious() is not None:
                        del parent[0]
            else:
                tag = _local(element.tag)
                if tag in fields and element.text and tag not in header:
                    header[tag] = element.text.strip()
    except etree.XMLSyntaxError as exc:
        raise FilingParseError() from exc

    if not holdings and not header:
        raise UnrecognizedFiling()

    def _dec(key: str) -> Decimal | None:
        raw = header.get(key)
        if raw is None:
            return None
        try:
            return Decimal(raw)
        except (InvalidOperation, ValueError):
            return None

    return Filing(
        cik=cik,
        registrant_name=header.get("regName"),
        series_name=meaningful(header.get("seriesName")),
        series_id=meaningful(header.get("seriesId")),
        filing_date=filing_date,
        period_end=header.get("repPdDate") or header.get("repPdEnd"),
        accession_number=accession_number,
        form_type=form_type,
        source_url=source_url,
        total_assets=_dec("totAssets"),
        net_assets=_dec("netAssets"),
        holdings=holdings,
    )
