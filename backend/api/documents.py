from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.document import Document
from backend.schemas.document import DocumentOut
from backend.services.document_service import register_document
from backend.services.file_validation import FileValidationError, validate_upload
from backend.services.storage import save_original
from database.connection import get_db

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        ext = validate_upload(file.filename, content)
    except FileValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    stored = save_original(content, ext)
    doc, duplicate = register_document(db, file.filename, ext, len(content), stored)
    return {"duplicate": duplicate, "document": DocumentOut.model_validate(doc)}


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.scalars(select(Document).order_by(Document.uploaded_at.desc())).all()


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc