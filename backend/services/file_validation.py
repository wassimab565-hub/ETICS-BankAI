from pathlib import Path

from backend.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
MAGIC_BYTES = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04",
}


class FileValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_upload(filename: str | None, content: bytes) -> str:
    """Validate extension, size and file signature. Returns the lowercase extension."""
    if not filename:
        raise FileValidationError("Missing filename.")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, XLSX.", 415
        )

    if len(content) == 0:
        raise FileValidationError("File is empty.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise FileValidationError(f"File too large. Max {settings.max_upload_mb} MB.", 413)

    if not content.startswith(MAGIC_BYTES[ext]):
        raise FileValidationError("File content does not match its extension.")

    return ext