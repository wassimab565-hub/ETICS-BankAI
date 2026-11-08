from pathlib import Path

from sqlalchemy import func, select

from ai_engine.extraction.schemas import (
    ExtractedField,
    ExtractionResult,
    FieldSource,
    ValidationStatus,
)
from backend.core.config import BASE_DIR
from backend.models.analysis import ExtractedFieldRow
from backend.models.document import Document
from backend.models.document_page import DocumentPage
from backend.services import analysis_repository as repo
from backend.services.page_repository import save_pages
from database.connection import SessionLocal
from document_processing.parsers.pdf_parser import parse_pdf
from document_processing.preprocessing.text_cleaner import clean_pages

db = SessionLocal()
doc = db.scalar(select(Document).order_by(Document.id).limit(1))
if doc is None or doc.file_type != "pdf":
    raise SystemExit("upload a PDF first (POST /documents/upload)")

pages = clean_pages(parse_pdf(BASE_DIR / doc.file_path))
print("pages saved:", save_pages(db, doc.id, pages))

run = repo.create_run(db, doc.id, "smoke-test", "extraction_smoke", "risk_smoke")
source = FieldSource(
    chunk_index=0, page_start=1, page_end=1, line_start=1, line_end=1, evidence="Tenue de compte 2,40 €"
)
field = ExtractedField(
    field_name="account_fee", raw_value="2,40", value_number=2.4, unit="EUR/month",
    source=source, status=ValidationStatus.valid,
)
repo.save_extraction(
    db, run, ExtractionResult(model_name="smoke-test", prompt_version="x", chunks_total=1, chunks_analyzed=1, fields=[field])
)
repo.finish_run(db, run)
row = repo.list_fields(db, run.id)[0]
repo.add_review(db, reviewer_name="smoke", decision="confirmed", field_id=row.id, corrected_value="2,50")
print("run:", run.id, run.status, "| fields:", len(run.fields), "| review:", row.reviews[0].corrected_value)

db.delete(run)  # cascade: fields and reviews must disappear too
db.commit()
print("after delete -> fields:", db.scalar(select(func.count()).select_from(ExtractedFieldRow)))
print("pages kept:", db.scalar(select(func.count()).select_from(DocumentPage)))