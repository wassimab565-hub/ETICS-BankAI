from dataclasses import dataclass


@dataclass
class PageText:
    page_number: int  # starts at 1
    text: str
    char_count: int