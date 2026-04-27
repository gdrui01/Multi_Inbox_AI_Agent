from __future__ import annotations

from pathlib import Path

import fitz


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json"}


def extract_text(file_path: str | Path) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in SUPPORTED_TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8")

    if suffix == ".pdf":
        return extract_text_from_pdf(path)

    raise ValueError(f"Unsupported file type: {suffix}")


def extract_text_from_pdf(file_path: str | Path) -> str:
    document = fitz.open(file_path)
    try:
        parts = [page.get_text("text") for page in document]
    finally:
        document.close()
    return "\n".join(parts).strip()
