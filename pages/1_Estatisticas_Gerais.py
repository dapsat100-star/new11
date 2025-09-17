# --- Config da página (deve ser a 1ª coisa do arquivo) ---
import streamlit as st
st.set_page_config(
    page_title="📊 Estatísticas Gerais",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS leve para mobile (margens menores e métricas mais confortáveis)
st.markdown("""
<style>
/* Margens menores em telas pequenas */
@media (max-width: 768px){
  .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
  [data-testid="stMetric"] { padding: 0.5rem 0.75rem; }
}
/* Garante que os iframes (ex.: folium) usem 100% da largura disponível */
iframe { width: 100% !important; }
</style>
""", unsafe_allow_html=True)

# --- Chrome / esconder itens padrão (opcional) ---
from ui_helpers import hide_streamlit_chrome
hide_streamlit_chrome(hide_header=True, hide_toolbar=True, hide_sidebar_nav=False)

# --- Guarda + Logout (cole no topo de cada página protegida) ---
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

# Botão de sair na sidebar quando autenticado
if st.session_state.get("authentication_status"):
    try:
        _auth.logout(location="sidebar")  # versões novas
    except Exception:
        _auth.logout("Sair", "sidebar")   # fallback versões antigas
else:
    st.warning("Sessão expirada. Faça login novamente.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()

# --- Conteúdo da página ---
st.title("📊 Estatísticas Gerais")

# 4 métricas: no desktop ficam lado a lado; no celular empilham automaticamente
c1, c2, c3, c4 = st.columns(4)
c1.metric("Relatórios OGMP 2.0", 48)
c2.metric("Aquisições de Satélite", 65)
c3.metric("Usuários Logados", 3)
c4.metric("Unidades Monitoradas", 10)

st.divider()
st.subheader("Mapa (exemplo simples)")

# Mapa responsivo: 100% da largura
try:
    import folium
    from streamlit_folium import st_folium

    # width="100%" faz o folium renderizar elástico; altura controlada pelo st_folium
    m = folium.Map(
        location=[-15.78, -47.93],
        zoom_start=4,
        tiles="cartodbpositron",
        control_scale=True,
        prefer_canvas=True,
        width="100%",   # <- chave para ocupar toda a largura
        height=480
    )

    for lat, lon, name in [
        (-3.13, -60.02, "Manaus"),
        (-22.90, -43.20, "Rio de Janeiro"),
        (-23.95, -46.33, "Santos"),
        (-30.03, -51.23, "Porto Alegre"),
    ]:
        folium.CircleMarker(location=[lat, lon], radius=6, tooltip=name).add_to(m)

    # NÃO fixe width aqui; deixe o componente expandir
    st_folium(m, height=480)
except Exception as e:
    st.info(f"Folium não disponível ou erro ao renderizar mapa: {e}")
