# -*- coding: utf-8 -*-
import os
import json
import base64
from pathlib import Path
from typing import Tuple, Dict, Any

import bcrypt
import requests
import streamlit as st
from PIL import Image
from dotenv import load_dotenv

# =========================
# CONFIGURAÇÃO INICIAL
# =========================
st.set_page_config(
    page_title="Plataforma OGMP 2.0",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
load_dotenv()

# =========================
# VARIÁVEIS DE AMBIENTE (SECRETS)
# =========================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
st.write("🔐 DEBUG: GITHUB_TOKEN carregado?", bool(GITHUB_TOKEN))
st.write("🔐 DEBUG: REPO_USERS =", REPO_USERS)

# Teste direto da API GitHub (sem login)
test_url = f"https://api.github.com/repos/{REPO_USERS}/contents/users.json"
r = requests.get(test_url, headers={"Authorization": f"Bearer {GITHUB_TOKEN}"})
st.write("🔐 DEBUG: GitHub status code =", r.status_code)
if r.status_code != 200:
    st.code(r.text)

REPO_USERS = os.getenv("REPO_USERS")               # dapsat100-star/new11
REPO_CRONOGRAMA = os.getenv("REPO_CRONOGRAMA")     # dapsat100-star/cronograma
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GH_DATA_ROOT = os.getenv("GH_DATA_ROOT", "data/validado")

HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

# =========================
# FUNÇÃO: BACKGROUND HERO
# =========================
def _bg_data_uri():
    here = Path(__file__).parent
    candidates = [here / "background.png", here / "assets" / "background.png"]
    for p in candidates:
        if p.exists():
            mime = "image/png"
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{b64}"
    return None

_bg = _bg_data_uri()
if _bg:
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"]::before {{
      content:"";
      position: fixed; inset: 0;
      z-index: 0; pointer-events: none;
      background: #f5f5f5 url('{_bg}') no-repeat center top;
      background-size: clamp(900px, 85vw, 1600px) auto;
      opacity: .5;
      filter: contrast(103%) brightness(101%);
    }}
    .block-container, [data-testid="stSidebar"], header, footer {{
      position: relative; z-index: 1;
    }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# ESTILOS HERO E LOGIN
# =========================
st.markdown("""
<style>
header[data-testid="stHeader"]{display:none!important;}
div[data-testid="stToolbar"]{display:none!important;}
#MainMenu{visibility:hidden;}
footer{visibility:hidden;}
[data-testid="stSidebarNav"]{ display:none !important; }
div[data-testid="collapsedControl"]{ display:block !important; }
.block-container{ padding-top: .5rem !important; }
* { color:#111 !important; }

.hero-wrap{ max-width: 560px; }
.logo-card{
  display:inline-block; background:#fff; padding:14px; border-radius:18px;
  box-shadow:0 6px 18px rgba(0,0,0,.06); border:1px solid #eee; margin-bottom:18px;
}
.hero-eyebrow{
  display:inline-block; font-size:12px; letter-spacing:.14em; text-transform:uppercase;
  padding:6px 12px; border:1px solid #cfcfcf; color:#222!important;
  border-radius:999px; background:#f7f7f7; margin:8px 0 14px 0;
}
.hero-title{
  font-size:44px; line-height:1.05; font-weight:900; letter-spacing:-0.02em;
  margin:8px 0 10px 0;
}
.hero-sub{ font-size:16px; color:#222; max-width:56ch; margin:0 0 10px 0; }
.hero-bullets{ margin:8px 0 18px 18px; }
.hero-bullets li{ margin:6px 0; }

.login-card{
  padding:24px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow:0 8px 24px rgba(0,0,0,.06); background:#fff;
}
</style>
""", unsafe_allow_html=True)

# =========================
# FUNÇÕES GITHUB (JSON)
# =========================
def github_load_json(repo: str, path: str) -> Tuple[Dict[str, Any], str | None]:
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content), data.get("sha")
    elif r.status_code == 404:
        st.error(f"Arquivo {path} não encontrado em {repo}.")
        return {}, None
    else:
        st.error(f"Erro ao acessar GitHub: {r.status_code} - {r.text}")
        return {}, None

def github_save_json(repo: str, path: str, content: dict, message: str, sha: str | None) -> bool:
    payload = {
        "message": message,
        "content": base64.b64encode(json.dumps(content, indent=2).encode()).decode(),
        "branch": GITHUB_BRANCH
    }
    if sha:
        payload["sha"] = sha
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    r = requests.put(url, headers=HEADERS, json=payload, timeout=15)
    return r.status_code in (200, 201)

# =========================
# LOGIN - USERS.JSON
# =========================
USERS_FILE = "users.json"

def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

# =========================
# HERO SECTION + LOGIN FORM
# =========================
left, right = st.columns([1.2, 1])

with left:
    st.markdown("<div class='hero-wrap'>", unsafe_allow_html=True)
    for cand in ("dapatlas.png","logo.png","logomavipe.jpeg"):
        if Path(cand).exists():
            st.markdown("<div class='logo-card'>", unsafe_allow_html=True)
            st.image(Image.open(cand), width=180)
            st.markdown("</div>", unsafe_allow_html=True)
            break
    st.markdown("<div class='hero-eyebrow'>OGMP 2.0 – L5</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-title'>Plataforma de Monitoramento de Metano por Satélite</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-sub'>Detecção, quantificação e relatórios automatizados de metano com dados multissatélite.</div>", unsafe_allow_html=True)
    st.markdown("""
    <ul class='hero-bullets'>
      <li>📡 Detecção e priorização de eventos</li>
      <li>📑 Relatórios OGMP 2.0 e auditoria</li>
      <li>📈 Geoportal com mapas e séries históricas</li>
    </ul>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.subheader("🔐 Acesso Seguro")
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    login_btn = st.button("Entrar")
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# AUTENTICAÇÃO
# =========================
if login_btn:
    users_cfg, users_sha = github_load_json(REPO_USERS, USERS_FILE)
    user_rec = users_cfg.get("users", {}).get(username)
    if not user_rec or not check_password(password, user_rec["password"]):
        st.error("Usuário ou senha inválidos.")
    else:
        st.session_state["user"] = username
        st.session_state["must_change"] = user_rec.get("must_change", False)
        st.session_state["users_sha"] = users_sha
        st.session_state["users_cfg"] = users_cfg
        st.experimental_rerun()

# =========================
# ÁREA AUTENTICADA
# =========================
if "user" in st.session_state and not st.session_state.get("must_change", False):
    st.sidebar.success(f"Logado como: {st.session_state['user']}")
    st.sidebar.markdown("## 📁 Módulos")
    for path, label, icon in [
        ("pages/2_Geoportal.py", "Geoportal", "🗺️"),
        ("pages/4_Agendamento_de_Imagens.py", "Agendamentos", "🗓️"),
        ("pages/3_Relatorio_OGMP_2_0.py", "Relatórios", "📄"),
        ("pages/1_Estatisticas_Gerais.py", "Estatísticas", "📊")
    ]:
        if Path(path).exists():
            st.sidebar.page_link(path, label=label, icon=icon)
    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.experimental_rerun()
    st.success("✅ Login realizado com sucesso.")

# =========================
# FOOTER
# =========================
st.markdown("""
<div style="margin-top:40px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#444;">
  DAP ATLAS · Ambiente: Produção · <a href="mailto:support@dapsistemas.com">Suporte</a>
</div>
""", unsafe_allow_html=True)
