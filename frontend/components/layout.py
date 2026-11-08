import streamlit as st

from frontend.api_client import ApiClient, ApiError

NOTICE = (
    "Aide à la revue : ces résultats sont générés par un modèle et doivent être "
    "vérifiés. Ils ne constituent pas un avis juridique."
)


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


@st.cache_data(ttl=10)
def _api_state(_client: ApiClient) -> dict:
    try:
        _client.health()
    except ApiError:
        return {"api": False, "model": False}
    try:
        model = bool(_client.ollama().get("model_available"))
    except ApiError:
        model = False
    return {"api": True, "model": model}


def safe_call(func, *args, **kwargs):
    """Call the API; on failure show the error and stop the page."""
    try:
        return func(*args, **kwargs)
    except ApiError as exc:
        st.error(str(exc))
        st.stop()


def render_sidebar() -> None:
    state = _api_state(get_client())
    with st.sidebar:
        st.markdown("### 🏦 ETICS")
        st.caption("Analyse de documents bancaires")
        st.write(("✅" if state["api"] else "❌") + " API")
        st.write(("✅" if state["model"] else "⚠️") + " Modèle Qwen3 (Ollama)")
        st.divider()
        st.caption(
            "Outil d'aide à la décision, pas une autorité juridique. "
            "La revue humaine reste indispensable."
        )