from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.audit_logger import AuditLogger
from src.d365_mock import MockD365Service
from src.decision_engine import DecisionEngine
from src.document_classifier import classify_document
from src.field_extractor import extract_fields
from src.human_review import ReviewQueue
from src.models import model_to_dict
from src.pdf_extraction import extract_text


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLE_DIR = DATA_DIR / "sample_documents"
OUTPUT_DIR = BASE_DIR / "outputs"
CONFIG_DIR = BASE_DIR / "config"
UPLOAD_DIR = OUTPUT_DIR / "uploads"


def ensure_runtime_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def load_sample_emails() -> list[dict]:
    path = DATA_DIR / "sample_emails.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_uploaded_file(uploaded_file) -> Path:
    target = UPLOAD_DIR / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    return target


def process_document(source_path: Path, mailbox: str | None = None, sender: str | None = None) -> dict:
    # Design inspiration: MatchFlow's architecture breakdown treats intake,
    # extraction, matching, and decisioning as separate steps. This function is
    # the local Streamlit-scale orchestrator for those steps.
    text = extract_text(source_path)
    classification = classify_document(text)
    document = extract_fields(
        text=text,
        source_name=source_path.name,
        source_path=str(source_path),
        classification=classification,
        mailbox=mailbox,
        sender=sender,
    )

    engine = DecisionEngine(CONFIG_DIR)
    d365 = MockD365Service(DATA_DIR)
    erp_result = d365.enrich_document(document, amount_tolerance_pct=engine.amount_tolerance_pct)
    decision = engine.decide(document, erp_result)

    review_queue = ReviewQueue(OUTPUT_DIR / "review_queue.csv")
    audit_logger = AuditLogger(
        audit_log_file=OUTPUT_DIR / "audit_log.csv",
        extracted_json_file=OUTPUT_DIR / "extracted_documents.json",
    )

    if decision.decision == "human_review":
        review_queue.add(document, decision)

    audit_logger.log_decision(document, decision)
    audit_logger.log_extracted_document(document, erp_result, decision)

    return {
        "document": document,
        "erp_result": erp_result,
        "decision": decision,
    }


def render_metrics() -> None:
    # Design inspiration: ypratap11/invoice-processing-ai surfaces operational
    # metrics in the UI. The three counters here are a lightweight local version.
    review_path = OUTPUT_DIR / "review_queue.csv"
    audit_path = OUTPUT_DIR / "audit_log.csv"

    review_df = pd.read_csv(review_path) if review_path.exists() and review_path.stat().st_size > 0 else pd.DataFrame()
    audit_df = pd.read_csv(audit_path) if audit_path.exists() and audit_path.stat().st_size > 0 else pd.DataFrame()

    col1, col2, col3 = st.columns(3)
    col1.metric("Processed Documents", len(audit_df))
    col2.metric("Open Review Items", len(review_df[review_df["status"] == "open"]) if not review_df.empty else 0)
    col3.metric("Auto-Routed", len(audit_df[audit_df["decision"] == "auto_route"]) if not audit_df.empty else 0)


def render_tables() -> None:
    # Design inspiration: lightweight workflow dashboards such as
    # ai-invoice-processing-automation make queue state and logs visible to the
    # operator. This app mirrors that idea with local CSV-backed tables.
    st.subheader("Review Queue")
    review_path = OUTPUT_DIR / "review_queue.csv"
    if review_path.exists() and review_path.stat().st_size > 0:
        st.dataframe(pd.read_csv(review_path), width="stretch")
    else:
        st.info("No items in the review queue yet.")

    st.subheader("Audit Log")
    audit_path = OUTPUT_DIR / "audit_log.csv"
    if audit_path.exists() and audit_path.stat().st_size > 0:
        st.dataframe(pd.read_csv(audit_path), width="stretch")
    else:
        st.info("No audit records yet.")


def main() -> None:
    ensure_runtime_dirs()
    st.set_page_config(page_title="Retail Purchase Inbox Agent", layout="wide")
    st.title("Retail Purchase Inbox Agent")
    st.caption("Prototype for multi-document intake, D365 enrichment, routing, review, and audit logging.")

    with st.sidebar:
        st.header("Document Intake")
        uploaded_file = st.file_uploader("Upload a document", type=["pdf", "txt", "md"])
        run_uploaded = st.button("Process uploaded document", width="stretch", disabled=uploaded_file is None)

        sample_emails = load_sample_emails()
        sample_options = {email["subject"]: email for email in sample_emails}
        selected_subject = st.selectbox("Or run a sample email", options=["None"] + list(sample_options.keys()))
        run_sample = st.button("Run sample email", width="stretch", disabled=selected_subject == "None")

    result = None

    if uploaded_file is not None and run_uploaded:
        file_path = save_uploaded_file(uploaded_file)
        result = process_document(file_path)

    elif selected_subject != "None" and run_sample:
        selected_email = sample_options[selected_subject]
        sample_path = SAMPLE_DIR / selected_email["attachment"]
        result = process_document(
            sample_path,
            mailbox=selected_email["mailbox"],
            sender=selected_email["sender"],
        )

    render_metrics()

    if result:
        st.subheader("Decision Summary")
        document = result["document"]
        decision = result["decision"]
        erp_result = result["erp_result"]

        left, middle, right = st.columns(3)
        left.metric("Document Type", document.document_type.replace("_", " ").title())
        middle.metric("Overall Confidence", f"{document.overall_confidence:.0%}")
        right.metric("Decision", decision.decision.replace("_", " ").title())

        st.write(f"**Target team:** {decision.target_team}")
        st.write(f"**Reason:** {decision.reason}")

        st.subheader("Extracted Fields")
        st.json(model_to_dict(document))

        st.subheader("Mock D365 Match")
        st.json(model_to_dict(erp_result))

    render_tables()


if __name__ == "__main__":
    main()
