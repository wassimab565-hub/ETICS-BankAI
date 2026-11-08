import streamlit as st

from frontend.components.layout import get_client, safe_call

st.title("📊 Tableau de bord")

stats = safe_call(get_client().stats)
col1, col2, col3 = st.columns(3)
col1.metric("Documents", stats["documents_total"])
col2.metric("À relire", stats["documents_by_status"].get("needs_review", 0))
col3.metric("Avec points à examiner", stats["documents_with_findings"])
st.caption(stats["notice"])
st.info("Les graphiques arrivent à l'étape 9.5.")