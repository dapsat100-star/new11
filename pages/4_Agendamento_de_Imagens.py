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
from datetime import date

st.title("🛰️ Agendamento de Imagens")

with st.form("agendar"):
    unidade = st.text_input("Nome da Unidade/Ativo", placeholder="Ex.: Plataforma P-XX")
    janela = st.date_input("Data desejada", value=date.today())
    prioridade = st.selectbox("Prioridade", ["Baixa", "Média", "Alta"])
    observ = st.text_area("Observações (opcional)")
    enviar = st.form_submit_button("Agendar")

if enviar:
    if not unidade:
        st.error("Informe o nome da Unidade/Ativo.")
    else:
        st.success(f"Solicitação registrada para **{unidade}** em **{janela}** (Prioridade: {prioridade}).")
        if observ:
            st.caption(f"Obs.: {observ}")
