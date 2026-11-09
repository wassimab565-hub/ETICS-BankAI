import streamlit as st

from frontend.components.documents_view import documents_to_rows
from frontend.components.labels import (
    DOCUMENT_TYPE_LABELS,
    PRIORITY_LABELS,
    STATUS_LABELS,
    label,
    priority_label,
)
from frontend.components.layout import get_client, safe_call

client = get_client()


def open_document(doc: dict) -> None:
    """Remember the chosen document for the other pages."""
    st.session_state["current_document"] = doc["id"]
    st.session_state["current_filename"] = doc["filename"]
    st.session_state["upload_duplicate"] = False


st.title("📁 Documents")

col_search, col_status, col_priority, col_type = st.columns([2, 1, 1, 1])
query = col_search.text_input("Rechercher par nom de fichier")
status = col_status.selectbox(
    "Statut", [None, *STATUS_LABELS], format_func=lambda v: "Tous" if v is None else STATUS_LABELS[v]
)
priority = col_priority.selectbox(
    "Priorité de revue",
    [None, *PRIORITY_LABELS],
    format_func=lambda v: "Toutes" if v is None else priority_label(v),
)
doc_type = col_type.selectbox(
    "Type",
    [None, *DOCUMENT_TYPE_LABELS],
    format_func=lambda v: "Tous" if v is None else DOCUMENT_TYPE_LABELS[v],
)

documents = safe_call(
    client.list_documents,
    status=status,
    review_priority=priority,
    document_type=doc_type,
    q=query or None,
)
if not documents:
    st.info("Aucun document ne correspond aux filtres.")
    st.stop()

st.caption(f"{len(documents)} document(s)")
event = st.dataframe(
    documents_to_rows(documents),
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
)
selected = event.selection.rows
if not selected:
    st.caption("Sélectionnez une ligne pour voir les actions disponibles.")
    st.stop()

doc = documents[selected[0]]
st.divider()
st.markdown(f"**{doc['filename']}** — {label(STATUS_LABELS, doc['status'])}")

if doc["status"] == "uploaded":
    if st.button("Lancer l'analyse", type="primary"):
        safe_call(client.start_analysis, doc["id"])
        open_document(doc)
        st.switch_page("pages/upload.py")
elif doc["status"] == "processing":
    if st.button("Voir la progression", type="primary"):
        open_document(doc)
        st.switch_page("pages/upload.py")
else:
    left, right = st.columns(2)
    if left.button("Voir les résultats", type="primary"):
        open_document(doc)
        st.switch_page("pages/results.py")
    if right.button("Relancer l'analyse"):
        safe_call(client.start_analysis, doc["id"])
        open_document(doc)
        st.switch_page("pages/upload.py")