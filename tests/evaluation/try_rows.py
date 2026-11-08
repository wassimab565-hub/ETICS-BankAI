import sys

import pymupdf

path, page_no = sys.argv[1], int(sys.argv[2])
page = pymupdf.open(path)[page_no]
tables = page.find_tables().tables
print(len(tables), "tables")

words = page.get_text("words")  # x0, y0, x1, y1, word, block, line, word_no
for table in tables:
    x0, y0, x1, y1 = table.bbox
    inside = [
        w for w in words
        if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1
    ]
    inside.sort(key=lambda w: (w[1] + w[3]) / 2)

    rows, row, anchor = [], [], None
    for w in inside:
        y = (w[1] + w[3]) / 2
        if anchor is None or abs(y - anchor) > 3:
            if row:
                rows.append(row)
            row, anchor = [], y
        row.append(w)
    if row:
        rows.append(row)

    for row in rows[:30]:
        print(" ".join(w[4] for w in sorted(row, key=lambda w: w[0])))