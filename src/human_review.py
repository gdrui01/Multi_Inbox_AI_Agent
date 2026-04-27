from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.models import DecisionResult, ExtractedDocument


class ReviewQueue:
    def __init__(self, output_file: str | Path):
        self.output_file = Path(output_file)

    def add(self, document: ExtractedDocument, decision: DecisionResult) -> None:
        # Design inspiration: marjaanah-stack/ai-invoice-processing-automation
        # and the AP workflow references both make review state explicit. This
        # prototype keeps that state in a simple CSV queue for demo purposes.
        record = pd.DataFrame(
            [
                {
                    "created_at": pd.Timestamp.utcnow().isoformat(),
                    "document_id": document.document_id,
                    "source_name": document.source_name,
                    "document_type": document.document_type,
                    "review_reason": decision.reason,
                    "status": "open",
                    "assigned_team": decision.target_team,
                    "po_number": document.po_number,
                    "vendor_name": document.vendor_name,
                    "total_amount": document.total_amount,
                }
            ]
        )
        self._append(record)

    def get_all(self) -> pd.DataFrame:
        if not self.output_file.exists():
            return pd.DataFrame()
        return pd.read_csv(self.output_file)

    def _append(self, record: pd.DataFrame) -> None:
        if self.output_file.exists() and self.output_file.stat().st_size > 0:
            existing = pd.read_csv(self.output_file)
            combined = pd.concat([existing, record], ignore_index=True)
        else:
            combined = record
        combined.to_csv(self.output_file, index=False)
