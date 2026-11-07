from pathlib import Path

from openpyxl import load_workbook

from document_processing.parsers.base import PageText


def parse_xlsx(path: str | Path) -> list[PageText]:
    """Extract each sheet as one 'page'. Empty cells and empty rows are skipped."""
    pages: list[PageText] = []
    wb = load_workbook(str(path), read_only=True, data_only=True)
    try:
        for index, ws in enumerate(wb.worksheets, start=1):
            lines = [f"[Sheet: {ws.title}]"]
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if cells:
                    lines.append(" | ".join(cells))
            text = "\n".join(lines)
            has_content = len(lines) > 1
            pages.append(
                PageText(
                    page_number=index,
                    text=text,
                    char_count=len(text.strip()) if has_content else 0,
                )
            )
    finally:
        wb.close()
    return pages