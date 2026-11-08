import sys
import threading
import time

from sqlalchemy import func, select

from backend.models.analysis import ExtractedFieldRow, RiskFindingRow
from backend.models.document import Document
from backend.services import analysis_repository as repo
from backend.services import progress
from backend.services.pipeline import run_pipeline
from database.connection import SessionLocal

document_id = int(sys.argv[1])
result: dict = {}
worker = threading.Thread(target=lambda: result.update(run_id=run_pipeline(document_id)))
started = time.time()
worker.start()

last = None
while worker.is_alive():
    state = progress.get(document_id)
    if state != last:
        print(f"[{time.time() - started:5.0f}s] {state}", flush=True)
        last = state
    time.sleep(2)
worker.join()
print(f"\nfinished in {time.time() - started:.0f}s | run id: {result.get('run_id')}")

with SessionLocal() as db:
    doc = db.get(Document, document_id)
    run = repo.get_run(db, result["run_id"])
    print(f"document: {doc.filename} -> {doc.status}")
    print(f"run: {run.status} | review priority: {run.review_priority} | error: {run.error}")
    print(
        f"extraction: {run.extraction_chunks_analyzed}/{run.extraction_chunks_total} chunks, failed {run.extraction_failed_chunks}"
    )
    print(
        f"risk: {run.risk_chunks_analyzed}/{run.risk_chunks_total} chunks, failed {run.risk_failed_chunks}"
    )
    by_status = db.execute(
        select(ExtractedFieldRow.status, func.count()).where(ExtractedFieldRow.run_id == run.id).group_by(ExtractedFieldRow.status)
    ).all()
    print("fields by status:", dict(by_status))
    by_severity = db.execute(
        select(RiskFindingRow.severity, func.count()).where(RiskFindingRow.run_id == run.id).group_by(RiskFindingRow.severity)
    ).all()
    print("findings by severity:", dict(by_severity))