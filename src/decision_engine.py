from __future__ import annotations

from pathlib import Path

import yaml

from src.models import DecisionResult, ERPMatchResult, ExtractedDocument


class DecisionEngine:
    def __init__(self, config_dir: str | Path):
        config_path = Path(config_dir)
        self.thresholds = yaml.safe_load((config_path / "thresholds.yaml").read_text(encoding="utf-8"))
        self.routing_rules = yaml.safe_load((config_path / "routing_rules.yaml").read_text(encoding="utf-8"))

    def decide(self, document: ExtractedDocument, erp_result: ERPMatchResult) -> DecisionResult:
        # Design inspiration:
        # - ypratap11/invoice-processing-ai: confidence should influence the
        #   workflow outcome, not just be displayed.
        # - ap_automation_agent description: exceptions should be routed to human
        #   review instead of pretending full autonomy.
        # The rule evaluation itself is local and YAML-driven.
        review_reasons: list[str] = []

        if document.missing_fields:
            review_reasons.append("missing_required_fields")
        review_reasons.extend(erp_result.notes)

        if document.classification_confidence < self.thresholds["classification_auto"]:
            review_reasons.append("low_classification_confidence")
        if document.extraction_confidence < self.thresholds["extraction_auto"]:
            review_reasons.append("low_extraction_confidence")
        if document.overall_confidence < self.thresholds["overall_auto"]:
            review_reasons.append("low_overall_confidence")

        forced_reasons = set(self.routing_rules["review_reasons_force_review"])
        forced_hit = any(reason in forced_reasons for reason in review_reasons)

        target_team = self._resolve_team(document, erp_result)

        if forced_hit or review_reasons:
            return DecisionResult(
                decision="human_review",
                target_team=target_team,
                reason=", ".join(sorted(set(review_reasons))),
                overall_confidence=document.overall_confidence,
                review_reasons=sorted(set(review_reasons)),
            )

        return DecisionResult(
            decision="auto_route",
            target_team=target_team,
            reason="Matched routing rules and confidence thresholds.",
            overall_confidence=document.overall_confidence,
            review_reasons=[],
        )

    def _resolve_team(self, document: ExtractedDocument, erp_result: ERPMatchResult) -> str:
        # Design inspiration: MatchFlow's layered architecture and the AP routing
        # examples we reviewed both treat assignment as a distinct step after
        # extraction and validation. This project resolves teams via config plus
        # ERP ownership metadata.
        country_routes = self.routing_rules["country_routes"]
        country_code = document.country_code or "AT"
        document_type = document.document_type

        if erp_result.owner_team:
            return erp_result.owner_team

        if country_code in country_routes and document_type in country_routes[country_code]:
            return country_routes[country_code][document_type]

        return self.routing_rules["default_team"]

    @property
    def amount_tolerance_pct(self) -> float:
        return float(self.thresholds["amount_tolerance_pct"])
