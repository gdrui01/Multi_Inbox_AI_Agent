from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# Design inspiration: ExtractThinker README "Basic Extraction Example" and
# "Classification Example". The influence here is the typed contract approach:
# keep extraction and classification outputs in stable models rather than
# passing loose dicts through the pipeline.
class LineItem(BaseModel):
    sku: str | None = None
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class ClassificationResult(BaseModel):
    document_type: str = "unknown"
    confidence: float = 0.0
    rationale: str = ""


class ExtractedDocument(BaseModel):
    document_id: str
    source_name: str
    source_path: str | None = None
    document_type: str = "unknown"
    classification_confidence: float = 0.0
    extraction_confidence: float = 0.0
    overall_confidence: float = 0.0
    document_number: str | None = None
    reference_number: str | None = None
    po_number: str | None = None
    vendor_name: str | None = None
    vendor_id: str | None = None
    document_date: str | None = None
    currency: str | None = None
    country_code: str | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    mailbox: str | None = None
    sender: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    raw_text: str = ""
    missing_fields: list[str] = Field(default_factory=list)


class ERPMatchResult(BaseModel):
    po_found: bool = False
    vendor_found: bool = False
    vendor_matches_po: bool = False
    currency_matches_po: bool = False
    amount_within_tolerance: bool = False
    business_unit: str | None = None
    cost_center: str | None = None
    owner_team: str | None = None
    po_expected_total: float | None = None
    notes: list[str] = Field(default_factory=list)


class DecisionResult(BaseModel):
    decision: str
    target_team: str
    reason: str
    overall_confidence: float
    review_reasons: list[str] = Field(default_factory=list)


class AuditRecord(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    document_id: str
    source_name: str
    document_type: str
    decision: str
    target_team: str
    reason: str
    overall_confidence: float
    po_number: str | None = None
    vendor_name: str | None = None
    total_amount: float | None = None


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
