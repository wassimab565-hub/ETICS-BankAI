import hashlib
from pathlib import Path

from backend.core.config import BASE_DIR, settings


def uploads_dir() -> Path:
    path = BASE_DIR / settings.data_dir / "raw" / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_original(content: bytes, ext: str) -> dict:
    """Store the original file as <sha256><ext>. Identical files are stored once."""
    sha256 = hashlib.sha256(content).hexdigest()
    path = uploads_dir() / f"{sha256}{ext}"
    duplicate = path.exists()
    if not duplicate:
        path.write_bytes(content)
    return {
        "sha256": sha256,
        "stored_path": path.relative_to(BASE_DIR).as_posix(),
        "duplicate": duplicate,
    }