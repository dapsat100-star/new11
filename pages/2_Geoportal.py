# -*- coding: utf-8 -*-
import streamlit as st
from pathlib import Path
from PIL import Image
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

st.set_page_config(
    page_title="Geoportal – OGMP 2.0 L5",
    page_icon="favicon.png",
    layout="wide",
    initial_sidebar_state="expanded",  # deixa a sidebar aberta
)

# ---- util: mostrar sidebar (caso algum CSS da Home aculte) ----
def force_show_sidebar():
    st.markdown("""
    <style>
      [data-testid='stSidebar']{display:flex !important;}
      div[data-testid="collapsedControl"]{display:block !important;}
    </style>
    """, unsafe_allow_html=True)

# ---- guard de sessão (não recrie o authenticator aqui) ----
# streamlit_authenticator define: st.session_state["authentication_status"] = True/False/None
auth_ok = st.session_state.get("authentication_status", None)
name = st.session_state.get("name") or st.session_state.get("username")

if not auth_ok:
    st.warning("Sessão expirada ou não autenticada.")
    # Link de volta para a Home / página de login
    # Ajuste o caminho abaixo conforme o nome do seu arquivo de entrada.
    st.page_link("Home.py", label="🔒 Voltar à página de login")
    st.stop()

# opcional: carrega o mesmo config para poder exibir o logout
def _build_authenticator():
    try:
        with open("auth_config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.load(f, Loader=SafeLoader)
        return stauth.Authenticate(
            cfg["credentials"], cfg["cookie"]["name"],
            cfg["cookie"]["key"], cfg["cookie"]["expiry_days"]
        )
    except Exception:
        return None

authenticator = _build_authenticator()

# ---- UI topo ----
force_show_sidebar()
st.sidebar.success(f"Logado como: {name or 'usuário'}")
if authenticator:
    try:
        authenticator.logout(location="sidebar")
    except Exception:
        authenticator.logout("Sair", "sidebar")

col_logo, col_title = st.columns([1, 4], vertical_alignment="center")
with col_logo:
    for cand in ("dapatlas.png","dapatlas.jpeg","logo.png","logo.jpeg"):
        if Path(cand).exists():
            st.image(Image.open(cand), width=140)
            break
with col_title:
    st.markdown("### Geoportal – Plataforma de Metano (OGMP 2.0 · L5)")
    st.caption("Mapas, KPIs e relatórios. Ambiente autenticado.")

st.divider()

# =========================
#   U P L O A D   D E   A R Q U I V O S
# =========================

# ► Se você quer o upload na SIDEBAR:
uploaded = st.sidebar.file_uploader(
    "📤 Carregar dados (Excel/CSV)",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=False,
    key="uploader_geoportal",
)

# ► Se preferir no CORPO da página, comente o bloco acima e use o abaixo:
# uploaded = st.file_uploader(
#     "📤 Carregar dados (Excel/CSV)",
#     type=["xlsx", "xls", "csv"],
#     accept_multiple_files=False,
#     key="uploader_geoportal",
# )

if not uploaded:
    st.info("Carregue um arquivo na sidebar para começar.")
    st.stop()

# =========================
#   T R A T A M E N T O   I N I C I A L
# =========================
from io import BytesIO
import pandas as pd

try:
    if uploaded.name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded)
    else:
        df = pd.read_csv(uploaded)
except Exception as e:
    st.error(f"Falha ao ler o arquivo: {e}")
    st.stop()

st.success(f"Arquivo carregado: **{uploaded.name}**  ·  {len(df):,} linhas")
st.dataframe(df.head(100), use_container_width=True)

# Aqui você continua com seus gráficos, mapas e KPIs...
# ex.: st.map(...), plotly, folium, etc.

