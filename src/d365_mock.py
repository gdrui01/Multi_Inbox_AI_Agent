from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.models import ERPMatchResult, ExtractedDocument


class MockD365Service:
    def __init__(self, data_dir: str | Path):
        data_path = Path(data_dir)
        self.po_df = pd.read_csv(data_path / "mock_d365_pos.csv")
        self.vendor_df = pd.read_csv(data_path / "mock_vendors.csv")
        self.cost_center_df = pd.read_csv(data_path / "mock_cost_centers.csv")

    def enrich_document(self, document: ExtractedDocument, amount_tolerance_pct: float) -> ERPMatchResult:
        # Design inspiration: MatchFlow's README architecture separates matching
        # from upload/extraction, and ap_automation_agent's public description
        # emphasizes validating documents against PO and vendor records before
        # routing. This method implements that validation locally with CSV-backed
        # mock D365 data.
        result = ERPMatchResult()

        vendor_row = self.vendor_df[self.vendor_df["vendor_name"].str.lower() == (document.vendor_name or "").lower()]
        if document.vendor_id:
            vendor_row = self.vendor_df[self.vendor_df["vendor_id"] == document.vendor_id]

        if not vendor_row.empty:
            result.vendor_found = True

        po_row = self.po_df[self.po_df["po_number"] == document.po_number]
        if not po_row.empty:
            result.po_found = True
            row = po_row.iloc[0]
            result.business_unit = row["business_unit"]
            result.cost_center = row["cost_center"]
            result.po_expected_total = float(row["expected_total"])
            result.currency_matches_po = (document.currency or "") == row["currency"]
            result.vendor_matches_po = (
                (document.vendor_id and document.vendor_id == row["vendor_id"])
                or ((document.vendor_name or "").lower() == str(row["vendor_name"]).lower())
            )

            if document.total_amount is not None:
                actual = abs(float(document.total_amount))
                expected = abs(float(row["expected_total"]))
                tolerance = max(expected * amount_tolerance_pct, 0.01)
                result.amount_within_tolerance = abs(actual - expected) <= tolerance

            owner_row = self.cost_center_df[self.cost_center_df["cost_center"] == row["cost_center"]]
            if not owner_row.empty:
                result.owner_team = owner_row.iloc[0]["owner_team"]

        if not result.po_found:
            result.notes.append("po_not_found")
        if result.po_found and not result.vendor_matches_po:
            result.notes.append("vendor_mismatch")
        if result.po_found and not result.currency_matches_po:
            result.notes.append("currency_mismatch")
        if result.po_found and not result.amount_within_tolerance:
            result.notes.append("amount_mismatch")

        return result
