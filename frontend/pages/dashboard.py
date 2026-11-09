import streamlit as st

from frontend.components.charts import (
    CATEGORY_CHART_LABELS,
    PRIORITY_CHART_LABELS,
    SEVERITY_CHART_LABELS,
    STATUS_CHART_LABELS,
    TYPE_CHART_LABELS,
    bar_figure,
    chart_series,
)
from frontend.components.documents_view import documents_to_rows
from frontend.components.layout import get_client, safe_call

client = get_client()


def show_chart(title: str, counts: dict, labels: dict) -> None:
    st.markdown(f"**{title}**")
    series = chart_series(counts, labels)
    if series:
        st.plotly_chart(bar_figure(series), use_container_width=True)
    else:
        st.caption("Aucune donnée.")


st.title("📊 Tableau de bord")

stats = safe_call(client.stats)
by_status = stats["documents_by_status"]

cols = st.columns(5)
cols[0].metric("Documents", stats["documents_total"])
cols[1].metric("À relire", by_status.get("needs_review", 0))
cols[2].metric("Analysés", by_status.get("processed", 0))
cols[3].metric("En cours", by_status.get("processing", 0))
cols[4].metric("Échecs", by_status.get("failed", 0))
st.metric("Documents avec des points à examiner", stats["documents_with_findings"])

left, right = st.columns(2)
with left:
    show_chart("Documents par statut", by_status, STATUS_CHART_LABELS)
    show_chart("Documents par type", stats["documents_by_type"], TYPE_CHART_LABELS)
    show_chart("Points à examiner par niveau estimé", stats["findings_by_severity"], SEVERITY_CHART_LABELS)
with right:
    show_chart(
        "Documents par priorité de revue",
        stats["documents_by_review_priority"],
        PRIORITY_CHART_LABELS,
    )
    show_chart("Points à examiner par catégorie", stats["findings_by_category"], CATEGORY_CHART_LABELS)

st.caption(stats["notice"])

st.subheader("Documents récents")
recent = safe_call(client.list_documents)[:5]
if recent:
    st.dataframe(documents_to_rows(recent), hide_index=True)
else:
    st.info("Aucun document pour le moment.")