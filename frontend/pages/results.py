import streamlit as st

from frontend.components.documents_view import format_date
from frontend.components.labels import (
    CATEGORY_LABELS,
    DOCUMENT_TYPE_LABELS,
    FIELD_LABELS,
    FIELD_STATUS_LABELS,
    STATUS_LABELS,
    label,
    priority_label,
)
from frontend.components.layout import get_client, safe_call
from frontend.components.results_view import (
    FIELD_STATUS_ICONS,
    analysis_summary,
    corrected_value,
    criteria_labels,
    escape_markdown,
    format_value,
    issue_label,
    latest_review,
    order_fields,
    page_text,
    review_summary,
    severity_label,
    split_findings,
)

client = get_client()


def render_review(item: dict) -> None:
    review = latest_review(item)
    if review:
        st.info("Revue humaine : " + review_summary(review))
    else:
        st.caption("Généré par le modèle, pas encore relu.")


def render_finding(finding: dict) -> None:
    with st.container(border=True):
        st.markdown(
            f"**{label(CATEGORY_LABELS, finding['category'])}** · "
            f"Niveau estimé : {severity_label(finding['severity'])} · {page_text(finding)}"
        )
        st.caption("Passage du document")
        st.markdown("> " + escape_markdown(finding["evidence"]))
        st.markdown("**Pourquoi signalé :** " + escape_markdown(finding["explanation"]))
        st.markdown("**Question / action suggérée :** " + escape_markdown(finding["suggested_action"]))
        reasons = criteria_labels(finding["criteria"])
        if reasons:
            st.markdown("**Critères retenus :**\n" + "\n".join(f"- {reason}" for reason in reasons))
        for issue in finding["issues"]:
            st.caption("⚠️ " + issue_label(issue))
        render_review(finding)


def render_field(field: dict) -> None:
    corrected = corrected_value(field)
    shown = f"{corrected} (corrigée)" if corrected else format_value(field)
    title = (
        f"{FIELD_STATUS_ICONS.get(field['status'], '•')} "
        f"{label(FIELD_LABELS, field['field_name'])} — {escape_markdown(shown)}"
    )
    with st.expander(title):
        st.caption(
            f"Contrôles automatiques : {label(FIELD_STATUS_LABELS, field['status'])} · {page_text(field)}"
        )
        st.markdown("**Valeur du modèle :** " + escape_markdown(field["raw_value"]))
        if field.get("label"):
            st.markdown("**Concerne :** " + escape_markdown(field["label"]))
        st.caption("Passage du document")
        st.markdown("> " + escape_markdown(field["evidence"]))
        for issue in field["issues"]:
            st.caption("⚠️ " + issue_label(issue))
        render_review(field)


st.title("🔍 Résultats")

documents = safe_call(client.list_documents)
analyzed = [d for d in documents if d["status"] in ("needs_review", "processed", "failed")]
if not analyzed:
    st.info("Aucun document analysé pour le moment. Téléversez un document puis lancez l'analyse.")
    st.stop()

names = {doc["id"]: doc["filename"] for doc in analyzed}
ids = list(names)
current = st.session_state.get("current_document")
document_id = st.selectbox(
    "Document", ids, index=ids.index(current) if current in ids else 0, format_func=names.get
)
st.session_state["current_document"] = document_id
st.session_state["current_filename"] = names[document_id]

results = safe_call(client.results, document_id)
run, document = results["run"], results["document"]

col1, col2, col3 = st.columns(3)
col1.metric("Statut", label(STATUS_LABELS, document["status"]))
col2.metric("Priorité de revue", priority_label(run["review_priority"]))
col3.metric("Type de document", label(DOCUMENT_TYPE_LABELS, document["document_type"]))
st.caption(
    f"Analyse n°{run['id']} · modèle {run['model_name']} · prompts "
    f"{run['extraction_prompt_version']} / {run['risk_prompt_version']} · "
    f"terminée le {format_date(run['finished_at'])}"
)
st.caption(
    "La priorité de revue est calculée automatiquement à partir des points détectés : "
    "elle n'indique pas la conformité du document."
)
st.warning(results["notice"])
for level, text in analysis_summary(results):
    getattr(st, level)(text)

findings, fields = results["findings"], results["fields"]
tab_findings, tab_fields = st.tabs(
    [f"Points à examiner ({len(findings)})", f"Informations extraites ({len(fields)})"]
)

with tab_findings:
    if not findings:
        st.write("Aucun point à examiner à afficher.")
    else:
        has_low = any(f["severity"] == "low" for f in findings)
        show_low = (
            st.toggle("Afficher aussi les points de faible priorité", value=False) if has_low else True
        )
        visible, hidden = split_findings(findings, show_low)
        if hidden:
            st.caption(f"{hidden} point(s) de faible priorité masqué(s).")
        for finding in visible:
            render_finding(finding)

with tab_fields:
    if not fields:
        st.write("Aucune information extraite.")
    else:
        st.caption(
            "« Contrôles OK » signifie que les vérifications automatiques sont passées, "
            "pas que la valeur est prouvée. Vérifiez le passage cité."
        )
        only_check = st.toggle("Afficher uniquement les éléments à vérifier", value=False)
        for field in order_fields(fields):
            if only_check and field["status"] == "valid":
                continue
            render_field(field)