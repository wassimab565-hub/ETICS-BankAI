from frontend.components.charts import (
    PRIORITY_CHART_LABELS,
    STATUS_CHART_LABELS,
    bar_figure,
    chart_series,
)


def test_chart_series_follows_the_label_order_and_skips_zero():
    counts = {"processed": 2, "needs_review": 1, "failed": 0}
    series = chart_series(counts, STATUS_CHART_LABELS)
    assert list(series.items()) == [("Analysé", 2), ("À relire", 1)]


def test_chart_series_keeps_unknown_values():
    series = chart_series({"low": 1, "not_assessed": 2, "weird": 3}, PRIORITY_CHART_LABELS)
    assert series == {"Faible": 1, "Non évaluée": 2, "weird": 3}


def test_bar_figure_is_horizontal_and_keeps_the_order():
    figure = bar_figure({"A": 2, "B": 1})
    bar = figure.data[0]
    assert list(bar.y) == ["A", "B"] and list(bar.x) == [2, 1]
    assert bar.orientation == "h"