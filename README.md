# Retail Purchase Inbox Agent

This repository contains a small interview prototype for a retail document-intelligence workflow. It demonstrates how incoming purchase-side documents can be ingested, classified, extracted, enriched with mock D365 data, routed automatically when confidence is high, and sent to human review when confidence or validation checks are not sufficient.

## Scope

The prototype supports:

- invoice intake
- credit note intake
- order confirmation intake
- mock D365 PO and vendor lookups
- routing rules by country and document type
- human review queue
- audit logging

## Tech Stack

- Streamlit
- Python
- PyMuPDF
- Pydantic
- pandas
- PyYAML

## Project Structure

```text
.
|-- app.py
|-- config/
|-- data/
|-- outputs/
`-- src/
```

## Run Locally

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
streamlit run app.py
```

or

```bash
python -m streamlit run app.py
```

If Streamlit cannot write to your user home directory in your environment, use the included launcher:

```powershell
.\run_app.ps1
```

The project disables Streamlit's source file watcher in `.streamlit/config.toml`. That avoids noisy `transformers`/`torchvision` inspection errors when the embedding-based classifier is loaded.

### Classification model note

The repository includes a trimmed local copy of the pretrained sentence-transformer used by the document classifier in `models/all-MiniLM-L6-v2`. That means a user who downloads the repo and installs `requirements.txt` does not need an additional model download step for classification.

## Demo Notes

The app can process uploaded `.pdf` and `.txt` files. It also includes sample documents wired through sample email metadata so the end-to-end flow can be demonstrated without external dependencies.

## Concrete Inspiration Map

No code from the referenced repositories was copied verbatim into this project. The table below maps the exact local code areas to the specific external pattern that influenced them.

| Local code | External reference | Exact borrowed idea | What was implemented here instead |
|---|---|---|---|
| [src/models.py] `LineItem`, `ClassificationResult`, `ExtractedDocument`, `ERPMatchResult`, `DecisionResult`, `AuditRecord` | `enoch3712/ExtractThinker` README examples for `InvoiceContract`, `Classification`, and typed extraction output | Keep document processing outputs in typed models instead of passing loose dictionaries between steps | Local Pydantic models for this retail workflow |
| [src/document_classifier.py]`classify_document()` | `enoch3712/ExtractThinker` classification example | Classification should be a separate stage that returns a document type and confidence before extraction begins | Local regex scoring for `invoice`, `credit_note`, and `order_confirmation` |
| [src/document_classifier.py]`infer_country()` | `Mouez-Yazidi/Multilingual-Invoice-Parsing-with-LLaMA-4` project framing | Multi-country documents need normalization signals before routing | Local heuristics from currency and country tokens |
| [src/field_extractor.py] `extract_fields()` | `enoch3712/ExtractThinker` README "Basic Extraction Example" | After classification, normalize the document into a stable structured object with line items and core business fields | Local regex extraction into `ExtractedDocument` |
| [src/field_extractor.py]`_calculate_extraction_confidence()` and `overall_confidence` handling | `ypratap11/invoice-processing-ai` feature framing around confidence scoring | Confidence should be part of the workflow payload, not just hidden model output | Local completeness-based confidence scoring |
| [src\d365_mock.py] `enrich_document()` | `datpham0412/invoice-processor` README architecture split around upload/extraction/matching, plus `umair801/ap_automation_agent` project description about PO and vendor validation | Matching and validation should live in a distinct step after extraction, and should check PO, vendor, currency, and amount before routing | Local CSV-backed mock D365 enrichment service |
| [src/decision_engine.py] `decide()` | `ypratap11/invoice-processing-ai` confidence-driven workflow framing and `umair801/ap_automation_agent` human-review routing description | Route automatically only when confidence and business rules are satisfied; otherwise create an exception path | Local YAML-driven rule engine returning `auto_route` or `human_review` |
| [src/decision_engine.py]`_resolve_team()` | `datpham0412/invoice-processor` layered workflow framing | Team assignment should be a separate post-validation step | Local country + document-type routing with optional ERP owner override |
| [src/human_review.py] `ReviewQueue.add()` | `marjaanah-stack/ai-invoice-processing-automation` lightweight approval/logging workflow idea | Exceptions should become explicit review items instead of silent failures | Local CSV review queue |
| [src/audit_logger.py] `log_decision()` and `log_extracted_document()` | `ypratap11/invoice-processing-ai` processing-history framing and `marjaanah-stack/ai-invoice-processing-automation` logging concept | Preserve both a compact audit trail and a more detailed structured record | Local CSV audit log plus JSON payload archive |
| [app.py]`process_document()` | `datpham0412/invoice-processor` architecture narrative | One orchestrator should call intake, extraction, matching, and decisioning in sequence | Local Streamlit orchestration function |
| [app.py] `render_metrics()` and `render_tables()` | `ypratap11/invoice-processing-ai` results-display idea and `marjaanah-stack/ai-invoice-processing-automation` operator-view idea | Show operational status to the user, not just raw extracted JSON | Local metrics cards and CSV-backed tables |

## Production Direction

For a production deployment, the recommended architecture would replace local files with Azure storage, Azure Document Intelligence, a workflow or orchestration layer, a database-backed audit store, and a real D365 integration service.
