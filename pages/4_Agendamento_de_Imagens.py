# -*- coding: utf-8 -*-
# pages/4_Agendamento_de_Imagens.py

from pathlib import Path
from typing import Optional, Dict
import io
import pandas as pd
import streamlit as st

# ====== Auth (logout + guard) ======
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# ----------------- Página -----------------
st.set_page_config(
    page_title="Agendamento de Imagens",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",  # ✅ sempre expandida
)

# === CSS: sidebar sempre aberta + sem botão de colapsar ===
st.markdown("""
<style>
/* Esconde cabeçalho nativo */
header[data-testid="stHeader"]{ display:none !important; }

/* Sidebar SEMPRE visível/expandida */
section[data-testid="stSidebar"], aside[data-testid="stSidebar"]{
  display:block !important;
  visibility:visible !important;
  transform:none !important;
}

/* Nunca mostrar o botão de colapsar */
div[data-testid="collapsedControl"]{ display:none !important; }

/* Remover menu multipágina nativo (usaremos page_link) */
div[data-testid="stSidebarNav"]{ display:none !important; }
section[data-testid="stSidebar"] nav,
section[data-testid="stSidebar"] [role="navigation"]{ display:none !important; }

/* Largura fixa pra não encolher */
@media (max-width:3000px){
  section[data-testid="stSidebar"]{
    min-width:300px !important;
    width:300px !important;
  }
}

/* Aproximar conteúdo do topo */
main.block-container{ padding-top:0.0rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("🗓️ Agendamento de Imagens")

# ---- Guard de sessão ----
auth_ok   = st.session_state.get("authentication_status", None)
user_name = st.session_state.get("name") or st.session_state.get("username")
if not auth_ok:
    st.warning("Sessão expirada ou não autenticada.")
    st.markdown('<a href="/" target="_self">🔒 Voltar à página de login</a>', unsafe_allow_html=True)
    st.stop()

# ============== Sidebar (logout + atalhos) ==============
def _build_authenticator():
    try:
        with open("auth_config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.load(f, Loader=SafeLoader)
        return stauth.Authenticate(
            cfg["credentials"],
            cfg["cookie"]["name"],
            cfg["cookie"]["key"],
            cfg["cookie"]["expiry_days"],
        )
    except Exception:
        return None

with st.sidebar:
    st.success(f"Logado como: {user_name or 'usuário'}")
    _auth = _build_authenticator()
    if _auth:
        try:
            _auth.logout(location="sidebar")
        except Exception:
            _auth.logout("Sair", "sidebar")
    st.markdown("---")

    # --- Atalhos para módulos (links fixos) ---
    st.markdown("### 🔗 Módulos")

    # Resolve caminhos tanto na raiz quanto em /pages
    def _first_existing(*cands):
        for p in cands:
            if Path(p).exists():
                return p
        # se nenhum existir, retorna o primeiro (Streamlit ignora se não existir)
        return cands[0]

    GEO_PAGE     = _first_existing("pages/2_Geoportal.py", "2_Geoportal.py")
    REL_PAGE     = _first_existing("pages/3_Relatorio_OGMP_2_0.py", "3_Relatorio_OGMP_2_0.py")
    ESTATS_PAGE  = _first_existing("pages/1_Estatisticas_Gerais.py", "1_Estatisticas_Gerais.py")

    st.page_link(GEO_PAGE,    label="GEOPORTAL",           icon="🗺️")
    st.page_link(REL_PAGE,    label="RELATÓRIO OGMP 2.0",  icon="📄")
    st.page_link(ESTATS_PAGE, label="ESTATÍSTICAS",        icon="📊")

    st.markdown("---")

    # ——— Parâmetros rápidos do agendamento (exemplo) ———
    st.header("⚙️ Parâmetros")
    constel = st.selectbox("Constelação", ["GHGSat", "Sentinel-2", "Landsat 8/9", "PlanetScope", "Capella", "ICEYE"])
    janela  = st.date_input("Janela de datas (início e fim)", [])
    prioridade = st.selectbox("Prioridade", ["Alta", "Média", "Baixa"], index=1)

# ============== Conteúdo principal (exemplo de esqueleto) ==============
st.subheader("Definir Área(s) de Interesse (AOI)")
col1, col2 = st.columns([1,1])

with col1:
    aoi_file = st.file_uploader("Upload de AOI (GeoJSON/KML/CSV WKT)", type=["geojson","kml","csv"])
    if aoi_file and aoi_file.name.lower().endswith(".csv"):
        try:
            df = pd.read_csv(aoi_file)
            st.dataframe(df.head(), use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao ler CSV: {e}")

with col2:
    st.write("Ou desenhe no mapa (a implementar):")
    st.caption("Nesta seção você pode integrar um componente de desenho para definir polígonos ou pontos.")

st.markdown("---")
st.subheader("Regras de Agendamento (demo)")
st.checkbox("Evitar horários fora da janela diurna")
st.checkbox("Evitar ângulo off-nadir acima de 25°")
st.checkbox("Permitir sobreposição com AOIs vizinhas (buffer 2 km)")

st.markdown("---")
st.subheader("Saídas")
st.caption("Aqui você pode exportar CSV/KML com as janelas previstas de aquisição.")
colA, colB = st.columns(2)
with colA:
    st.button("📤 Exportar CSV", type="secondary", use_container_width=True)
with colB:
    st.button("📤 Exportar KML", type="secondary", use_container_width=True)

st.info("Este é um esqueleto funcional com sidebar fixa, logout e navegação. Plugue aqui sua lógica de cálculo de passagens/overpass.")
