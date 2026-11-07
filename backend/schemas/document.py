from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    size_bytes: int
    sha256: str
    document_type: str | None
    status: str
    review_priority: str | None
    uploaded_at: datetime