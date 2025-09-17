from ui_helpers import hide_streamlit_chrome
hide_streamlit_chrome(hide_header=True, hide_toolbar=True, hide_sidebar_nav=False)

# --- Guarda + Logout (cole no topo de cada página) ---
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

with open("auth_config.yaml") as _f:
    _cfg = yaml.load(_f, Loader=SafeLoader)

_auth = stauth.Authenticate(
    _cfg["credentials"],
    _cfg["cookie"]["name"],
    _cfg["cookie"]["key"],
    _cfg["cookie"]["expiry_days"],
)

# Se a sessão está autenticada, mostra o botão Sair na sidebar
if st.session_state.get("authentication_status"):
    try:
        # versões novas podem aceitar apenas location=
        _auth.logout(location="sidebar")
    except Exception:
        # versões antigas requerem (label, location)
        _auth.logout("Sair", "sidebar")
else:
    st.warning("Sessão expirada. Faça login novamente.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
# --- fim do bloco de guarda + logout ---

import streamlit as st

st.title("🗺️ Geoportal")
st.write("Espaço para camadas geoespaciais, filtros e visualizações avançadas.")

st.divider()
st.subheader("Upload de camadas (GeoJSON, CSV, etc.)")
up = st.file_uploader("Envie um arquivo (ex.: GeoJSON/CSV)", type=["geojson","json","csv"])
if up is not None:
    st.success(f"Arquivo recebido: {up.name}")
    if up.name.lower().endswith(".csv"):
        import pandas as pd
        df = pd.read_csv(up)
        st.dataframe(df.head())
