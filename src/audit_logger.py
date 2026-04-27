from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.models import AuditRecord, ExtractedDocument, DecisionResult, ERPMatchResult, model_to_dict


class AuditLogger:
    def __init__(self, audit_log_file: str | Path, extracted_json_file: str | Path):
        self.audit_log_file = Path(audit_log_file)
        self.extracted_json_file = Path(extracted_json_file)

    def log_decision(self, document: ExtractedDocument, decision: DecisionResult) -> None:
        # Design inspiration: ypratap11/invoice-processing-ai highlights
        # processing history, while marjaanah-stack's workflow demo keeps simple
        # operational logs. This prototype records the decision layer in CSV.
        record = AuditRecord(
            document_id=document.document_id,
            source_name=document.source_name,
            document_type=document.document_type,
            decision=decision.decision,
            target_team=decision.target_team,
            reason=decision.reason,
            overall_confidence=decision.overall_confidence,
            po_number=document.po_number,
            vendor_name=document.vendor_name,
            total_amount=document.total_amount,
        )
        frame = pd.DataFrame([model_to_dict(record)])
        if self.audit_log_file.exists() and self.audit_log_file.stat().st_size > 0:
            existing = pd.read_csv(self.audit_log_file)
            frame = pd.concat([existing, frame], ignore_index=True)
        frame.to_csv(self.audit_log_file, index=False)

    def log_extracted_document(
        self,
        document: ExtractedDocument,
        erp_result: ERPMatchResult,
        decision: DecisionResult,
    ) -> None:
        # Keep the full structured payload for traceability alongside the compact
        # audit CSV. The JSON format is local to this project.
        current_payload: list[dict] = []
        if self.extracted_json_file.exists():
            current_payload = json.loads(self.extracted_json_file.read_text(encoding="utf-8") or "[]")

        current_payload.append(
            {
                "document": model_to_dict(document),
                "erp_result": model_to_dict(erp_result),
                "decision": model_to_dict(decision),
            }
        )
        self.extracted_json_file.write_text(json.dumps(current_payload, indent=2), encoding="utf-8")
