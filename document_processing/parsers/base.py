from dataclasses import dataclass


@dataclass
class PageText:
    page_number: int  # starts at 1
    text: str
    char_count: int
    ocr_used: bool = False
    ocr_confidence: float | None = None  # average word confidence (0-100)