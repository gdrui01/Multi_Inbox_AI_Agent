from __future__ import annotations

import re
from pathlib import Path

from src.document_classifier import infer_country
from src.models import ClassificationResult, ExtractedDocument, LineItem

# Design inspiration: ExtractThinker README "Basic Extraction Example". The
# borrowed idea is schema-first extraction: first decide the document type, then
# normalize fields into a stable typed object. The actual regex extraction below
# is local to this prototype.

FIELD_PATTERNS = {
    "vendor_name": [r"(?m)^Vendor:\s*(.+)$"],
    "vendor_id": [r"(?m)^Vendor ID:\s*(.+)$"],
    "po_number": [r"(?m)^PO Number:\s*([A-Z0-9\-]+)$"],
    "document_date": [r"(?m)^Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})$"],
    "currency": [r"(?m)^Currency:\s*([A-Z]{3})$"],
    "country_code": [r"(?m)^Country:\s*([A-Z]{2})$"],
    "subtotal": [r"(?m)^Subtotal:\s*(-?[0-9]+(?:\.[0-9]+)?)$"],
    "tax_amount": [r"(?m)^Tax:\s*(-?[0-9]+(?:\.[0-9]+)?)$"],
    "total_amount": [r"(?m)^Total:\s*(-?[0-9]+(?:\.[0-9]+)?)$"],
}

DOCUMENT_NUMBER_PATTERNS = {
    "invoice": [r"(?m)^Invoice Number:\s*([A-Z0-9\-]+)$"],
    "credit_note": [r"(?m)^Credit Note Number:\s*([A-Z0-9\-]+)$"],
    "order_confirmation": [r"(?m)^Confirmation Number:\s*([A-Z0-9\-]+)$"],
}

REFERENCE_PATTERNS = {
    "credit_note": [r"(?m)^Original Invoice:\s*([A-Z0-9\-]+)$"],
}

LINE_ITEM_PATTERN = re.compile(
    r"-\s*SKU:\s*(?P<sku>[^|]+)\|\s*Description:\s*(?P<description>[^|]+)\|\s*Quantity:\s*(?P<quantity>[^|]+)\|\s*Unit Price:\s*(?P<unit_price>[^|]+)\|\s*Amount:\s*(?P<amount>[^\n]+)"
)


def _extract_first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_line_items(text: str) -> list[LineItem]:
    items: list[LineItem] = []
    for match in LINE_ITEM_PATTERN.finditer(text):
        items.append(
            LineItem(
                sku=match.group("sku").strip(),
                description=match.group("description").strip(),
                quantity=_extract_float(match.group("quantity")),
                unit_price=_extract_float(match.group("unit_price")),
                amount=_extract_float(match.group("amount")),
            )
        )
    return items


def extract_fields(
    text: str,
    source_name: str,
    classification: ClassificationResult,
    source_path: str | None = None,
    mailbox: str | None = None,
    sender: str | None = None,
) -> ExtractedDocument:
    # Design inspiration: the classification-then-extraction split comes from
    # ExtractThinker-style pipelines. This function is the concrete local
    # implementation of that split for invoice, credit note, and order
    # confirmation samples.
    document_type = classification.document_type
    document_number = _extract_first(DOCUMENT_NUMBER_PATTERNS.get(document_type, []), text)
    reference_number = _extract_first(REFERENCE_PATTERNS.get(document_type, []), text)

    extracted = ExtractedDocument(
        document_id=_build_document_id(source_name, document_type, document_number),
        source_name=source_name,
        source_path=source_path,
        document_type=document_type,
        classification_confidence=classification.confidence,
        document_number=document_number,
        reference_number=reference_number,
        mailbox=mailbox,
        sender=sender,
        raw_text=text,
    )

    for field_name, patterns in FIELD_PATTERNS.items():
        raw_value = _extract_first(patterns, text)
        if field_name in {"subtotal", "tax_amount", "total_amount"}:
            setattr(extracted, field_name, _extract_float(raw_value))
        else:
            setattr(extracted, field_name, raw_value)

    if not extracted.country_code:
        extracted.country_code = infer_country(text)

    # Design inspiration: ypratap11/invoice-processing-ai treats confidence as a
    # first-class output alongside extracted fields. Here the confidence values
    # are computed locally from field completeness rather than copied from that repo.
    extracted.line_items = _extract_line_items(text)
    extracted.missing_fields = _calculate_missing_fields(extracted)
    extracted.extraction_confidence = _calculate_extraction_confidence(extracted)
    extracted.overall_confidence = round(
        (extracted.classification_confidence + extracted.extraction_confidence) / 2,
        2,
    )
    return extracted


def _build_document_id(source_name: str, document_type: str, document_number: str | None) -> str:
    base = document_number or Path(source_name).stem.upper()
    return f"{document_type[:3].upper()}-{base}"


def _calculate_missing_fields(document: ExtractedDocument) -> list[str]:
    required = ["document_number", "po_number", "vendor_name", "total_amount"]
    missing = []
    for field_name in required:
        value = getattr(document, field_name)
        if value in (None, "", []):
            missing.append(field_name)
    return missing


def _calculate_extraction_confidence(document: ExtractedDocument) -> float:
    present_fields = 0
    scored_fields = [
        document.document_number,
        document.po_number,
        document.vendor_name,
        document.total_amount,
        document.document_date,
        document.currency,
        document.country_code,
    ]
    for value in scored_fields:
        if value not in (None, ""):
            present_fields += 1
    return round(present_fields / len(scored_fields), 2)
