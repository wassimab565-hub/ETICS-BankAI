import streamlit as st

from frontend.components.labels import STATUS_LABELS, label
from frontend.components.layout import get_client, safe_call
from frontend.components.progress import is_final, outcome, progress_fraction, progress_text

client = get_client()


@st.fragment(run_every=2)
def analysis_progress(document_id: int) -> None:
    """Refreshes itself every 2 seconds, then reruns the page when the analysis is over."""
    status = safe_call(get_client().status, document_id)
    if is_final(status):
        st.rerun()
    st.progress(progress_fraction(status), text=progress_text(status))


st.title("📤 Téléverser un document")
st.caption("Formats acceptés : PDF, DOCX, XLSX (20 Mo maximum).")

uploaded = st.file_uploader("Choisissez un document bancaire", type=["pdf", "docx", "xlsx"])
if uploaded is not None and st.button("Téléverser le document", type="primary"):
    result = safe_call(client.upload, uploaded.name, uploaded.getvalue())
    st.session_state["current_document"] = result["document"]["id"]
    st.session_state["current_filename"] = result["document"]["filename"]
    st.session_state["upload_duplicate"] = result["duplicate"]

document_id = st.session_state.get("current_document")
if document_id is None:
    st.info("Téléversez un document pour commencer.")
    st.stop()

status = safe_call(client.status, document_id)
st.divider()
if st.session_state.get("upload_duplicate"):
    st.info("Un document identique existe déjà : le fichier n'a pas été enregistré une seconde fois.")
st.markdown(
    f"**Document :** {st.session_state.get('current_filename', document_id)}  \n"
    f"**Statut :** {label(STATUS_LABELS, status['status'])}"
)

if status["status"] == "processing":
    st.caption(
        "L'analyse peut durer de quelques secondes à plusieurs minutes selon la taille "
        "du document."
    )
    analysis_progress(document_id)
else:
    level, text = outcome(status)
    if level:
        getattr(st, level)(text)
    if status.get("error"):
        st.caption(f"Détail technique : {status['error']}")

    button_label = "Lancer l'analyse" if status["status"] == "uploaded" else "Relancer l'analyse"
    if st.button(button_label, type="primary"):
        safe_call(client.start_analysis, document_id)
        st.rerun()
    if status["status"] != "uploaded":
        st.page_link("pages/results.py", label="Voir les résultats", icon="🔍")