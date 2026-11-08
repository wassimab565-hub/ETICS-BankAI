from document_processing.parsers.table_rows import group_words_into_rows


def w(x0, y0, x1, y1, text):
    return (x0, y0, x1, y1, text, 0, 0, 0)


def test_words_at_same_height_form_one_row():
    words = [
        w(200, 10, 240, 20, "2,40"),
        w(10, 11, 60, 21, "Tenue"),
        w(250, 10, 260, 20, "€"),
        w(10, 40, 60, 50, "Actif"),
    ]
    assert group_words_into_rows(words) == ["Tenue 2,40 €", "Actif"]


def test_no_words_gives_no_rows():
    assert group_words_into_rows([]) == []