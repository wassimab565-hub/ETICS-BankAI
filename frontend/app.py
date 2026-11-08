import streamlit as st

from frontend.components.layout import render_sidebar

st.set_page_config(
    page_title="ETICS — Analyse de documents bancaires", page_icon="🏦", layout="wide"
)

pages = [
    st.Page("pages/dashboard.py", title="Tableau de bord", icon="📊", default=True),
    st.Page("pages/documents.py", title="Documents", icon="📁"),
    st.Page("pages/upload.py", title="Téléverser", icon="📤"),
    st.Page("pages/results.py", title="Résultats", icon="🔍"),
]

page = st.navigation(pages)
render_sidebar()
page.run()