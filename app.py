# ===== Seletor de idioma com bandeiras (topo esquerdo) =====
import base64
from pathlib import Path
import streamlit as st
import urllib.parse as _u

# estado de idioma default
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

# lê ?lang=pt|en da URL (opcional)
params = st.experimental_get_query_params()
if "lang" in params:
    _lang = (params["lang"][0] or "").lower()
    if _lang in ("pt", "en"):
        st.session_state.lang = _lang

# função utilitária para embutir imagem SVG/PNG em base64
def _img_b64(path: str) -> str:
    p = Path(path)
    mime = "image/svg+xml" if p.suffix.lower()==".svg" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")

# carrega bandeiras da raiz do repositório
BR = _img_b64("br.svg")
GB = _img_b64("gb.svg")

# CSS fixando a pílula no canto superior esquerdo
st.markdown("""
<style>
.lang-pill {
  position:fixed; top:16px; left:16px; z-index:9999;
  display:inline-flex; align-items:center; gap:8px;
  background:#ffffff; border:1px solid #e5e7eb; border-radius:999px;
  padding:6px 10px; box-shadow:0 8px 20px rgba(0,0,0,.08);
}
.lang-pill img { height:20px; width:auto; cursor:pointer; opacity:.8; transition:opacity .2s ease; }
.lang-pill img:hover { opacity:1; }
.lang-pill .active { opacity:1 !important; }
</style>
""", unsafe_allow_html=True)

is_pt = (st.session_state.lang == "pt")
pt_cls = "active" if is_pt else ""
en_cls = "active" if not is_pt else ""

# HTML com os ícones clicáveis (link troca a URL ?lang=)
st.markdown(
    f"""
    <div class="lang-pill">
      <a href="?lang=pt"><img class="{pt_cls}" src="{BR}" alt="PT" /></a>
      <a href="?lang=en"><img class="{en_cls}" src="{GB}" alt="EN" /></a>
    </div>
    """,
    unsafe_allow_html=True
)
# ===== Fim do seletor =====

