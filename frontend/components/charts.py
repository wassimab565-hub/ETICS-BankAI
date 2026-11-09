import plotly.graph_objects as go

from frontend.components.labels import CATEGORY_LABELS, DOCUMENT_TYPE_LABELS, STATUS_LABELS

STATUS_CHART_LABELS = {**STATUS_LABELS, "unknown": "Inconnu"}
PRIORITY_CHART_LABELS = {
    "low": "Faible",
    "medium": "Moyenne",
    "high": "Élevée",
    "not_assessed": "Non évaluée",
}
TYPE_CHART_LABELS = {**DOCUMENT_TYPE_LABELS, "unknown": "Non déterminé"}
SEVERITY_CHART_LABELS = {"low": "Faible", "medium": "Moyen", "high": "Élevé"}
CATEGORY_CHART_LABELS = dict(CATEGORY_LABELS)


def chart_series(counts: dict[str, int], labels: dict[str, str]) -> dict[str, int]:
    """Counts renamed with French labels, in the order of the labels, without zero counts.

    Values missing from the labels are kept with their raw name, never dropped.
    """
    series = {text: counts[key] for key, text in labels.items() if counts.get(key)}
    for key, value in counts.items():
        if key not in labels and value:
            series[key] = value
    return series


def bar_figure(series: dict[str, int]) -> go.Figure:
    names = list(series)
    values = [series[name] for name in names]
    figure = go.Figure(
        go.Bar(x=values, y=names, orientation="h", text=values, textposition="outside")
    )
    figure.update_layout(
        height=max(160, 46 * len(names) + 60),
        margin=dict(l=0, r=30, t=10, b=10),
        yaxis=dict(autorange="reversed"),
        xaxis=dict(showgrid=False, dtick=1, rangemode="tozero"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure