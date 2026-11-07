from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.file_validation import FileValidationError, validate_upload
from backend.services.storage import save_original

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    try:
        ext = validate_upload(file.filename, content)
    except FileValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    stored = save_original(content, ext)
    return {
        "filename": file.filename,
        "extension": ext,
        "size_bytes": len(content),
        **stored,
    }