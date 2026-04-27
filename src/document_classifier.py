from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any, cast

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.mixture import BayesianGaussianMixture

from src.models import ClassificationResult


# Design inspiration: ExtractThinker separates document classification from
# downstream extraction, and its examples return a typed classification result
# with confidence. This module keeps that split but replaces the old regex
# scorer with pretrained sentence embeddings plus a small Bayesian mixture model
# over seeded document examples.
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
LOCAL_MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "all-MiniLM-L6-v2"

DOCUMENT_SEEDS = {
    "invoice": [
        "Document Type: Invoice. Invoice Number: INV-1001. PO Number: PO-1001. Vendor invoice with subtotal, tax, and total amount due.",
        "Accounts payable invoice document listing Vendor, Vendor ID, Invoice Number, Date, Currency, PO Number, Subtotal, Tax, and Total.",
        "Supplier invoice for delivered goods with line items, invoice date, purchase order reference, and total payable amount.",
    ],
    "credit_note": [
        "Document Type: Credit Note. Credit Note Number: CN-2002. Original Invoice: INV-102. Supplier credit note with negative subtotal, negative tax, and negative total.",
        "Supplier credit memo referencing an original invoice and refunding or reversing a previous billed amount.",
        "Credit note document with credited line items, original invoice reference, and negative totals.",
    ],
    "order_confirmation": [
        "Document Type: Order Confirmation. Confirmation Number: OC-3003. PO Number: PO-3003. Supplier order confirmation acknowledging the order and confirming delivery details.",
        "Supplier order confirmation document with confirmation number, accepted order lines, quantity, price, and shipment details.",
        "Procurement order acceptance notice confirming a purchase order, delivery schedule, and logistics details.",
    ],
}

UNKNOWN_CONFIDENCE_THRESHOLD = 0.45

COUNTRY_PATTERNS = {
    "AT": [r"\bAT\b", r"\baustria\b", r"\beur\b"],
    "CH": [r"\bCH\b", r"\bswitzerland\b", r"\bchf\b"],
    "CZ": [r"\bCZ\b", r"\bczech\b", r"\bczk\b"],
}


@lru_cache(maxsize=1)
def _load_embedding_model() -> SentenceTransformer:
    model_name_or_path = str(LOCAL_MODEL_DIR) if LOCAL_MODEL_DIR.exists() else EMBEDDING_MODEL_NAME
    return SentenceTransformer(model_name_or_path)


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


@lru_cache(maxsize=1)
def _build_classifier_assets() -> dict[str, Any]:
    model = _load_embedding_model()
    label_centroids: dict[str, np.ndarray] = {}
    for label in DOCUMENT_SEEDS:
        label_seed_embeddings = np.asarray(model.encode(DOCUMENT_SEEDS[label], normalize_embeddings=True))
        label_vectors = label_seed_embeddings
        label_centroids[label] = _normalize_rows(label_vectors.mean(axis=0, keepdims=True))[0]

    centroid_matrix = np.asarray([label_centroids[label] for label in DOCUMENT_SEEDS])
    mixture = BayesianGaussianMixture(
        n_components=len(DOCUMENT_SEEDS),
        covariance_type="diag",
        random_state=42,
        max_iter=500,
        reg_covar=1e-3,
    )
    mixture.fit(centroid_matrix)
    centroid_component_probs = mixture.predict_proba(centroid_matrix)
    component_label_map: dict[int, str] = {}
    for label_idx, label in enumerate(DOCUMENT_SEEDS):
        component_label_map[int(np.argmax(centroid_component_probs[label_idx]))] = label

    return {
        "mixture": mixture,
        "label_centroids": label_centroids,
        "component_label_map": component_label_map,
    }


def classify_document(text: str) -> ClassificationResult:
    normalized = " ".join(text.lower().split())
    #empty text
    if not normalized:
        return ClassificationResult(
            document_type="unknown",
            confidence=0.2,
            rationale="The document text was empty after normalization.",
        )

    assets = _build_classifier_assets()
    embedding_model = _load_embedding_model()
    embedding = np.asarray(embedding_model.encode([normalized], normalize_embeddings=True))

    mixture = cast(BayesianGaussianMixture, assets["mixture"])
    label_centroids = cast(dict[str, np.ndarray], assets["label_centroids"])
    component_label_map = cast(dict[int, str], assets["component_label_map"])

    component_probs = mixture.predict_proba(embedding)[0]
    cluster_scores = {label: 0.0 for label in DOCUMENT_SEEDS}
    for component_idx, probability in enumerate(component_probs):
        label = component_label_map.get(component_idx)
        if label:
            cluster_scores[label] += float(probability)

    vector = embedding[0]
    cosine_scores = {
        label: max(0.0, float(np.dot(vector, centroid)))
        for label, centroid in label_centroids.items()
    }
    cosine_total = sum(cosine_scores.values()) or 1.0
    normalized_cosine_scores = {
        label: score / cosine_total
        for label, score in cosine_scores.items()
    }

    combined_scores = {
        label: 0.7 * cluster_scores[label] + 0.3 * normalized_cosine_scores[label]
        for label in DOCUMENT_SEEDS
    }
    document_type = max(combined_scores, key=combined_scores.get)
    confidence = round(min(combined_scores[document_type], 0.99), 2)

    if confidence < UNKNOWN_CONFIDENCE_THRESHOLD:
        return ClassificationResult(
            document_type="unknown",
            confidence=confidence,
            rationale="The Bayesian embedding classifier did not find a confident cluster match.",
        )

    rationale = (
        f"Assigned to the {document_type.replace('_', ' ')} cluster using "
        f"Bayesian prototype-cluster probability {cluster_scores[document_type]:.2f} and "
        f"embedding similarity {normalized_cosine_scores[document_type]:.2f}."
    )

    return ClassificationResult(
        document_type=document_type,
        confidence=confidence,
        rationale=rationale,
    )


def infer_country(text: str) -> str | None:
    # Design inspiration: Mouez-Yazidi/Multilingual-Invoice-Parsing-with-LLaMA-4
    # pushed the multi-country angle. Here that becomes a tiny local heuristic so
    # routing can distinguish AT/CH/CZ documents without a full multilingual model.
    normalized = text.lower()
    for country_code, patterns in COUNTRY_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            return country_code
    return None
