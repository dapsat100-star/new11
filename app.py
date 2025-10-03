# -*- coding: utf-8 -*-
import os
import json
import base64
import requests
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import streamlit as st
from PIL import Image
from dotenv import load_dotenv
import bcrypt

# =========================
# CONFIGURAÇÃO BÁSICA
# =========================
st.set_page_config(
    page_title="Plataforma de Metano OGMP 2.0 - L5",
    page_icon="favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)
load_dotenv()

# =========================
# ESTILOS
# =========================
st.markdown("""
<style>
header[data-testid="stHeader"]{display:none!important;}
div[data-testid="stToolbar"]{display:none!important;}
#MainMenu{visibility:hidden;}
footer{visibility:hidden;}
[data-testid="stSidebarNav"]{ display:none !important; }
div[data-testid="collapsedControl"]{ display:block !important; }
[data-testid="stAppViewContainer"]{ padding-top: 0 !important; }
.block-container{ padding-top: .5rem !important; }
.lang-row{ position:absolute; top:8px; left:16px; }
* { color:#111111 !important; }
a { color:#111111 !important; text-decoration: underline; }
input, textarea, select, .stTextInput input, .stPassword input {
  background:#ffffff !important; color:#111111 !important;
  border:1px solid #d0d7e2 !important; border-radius:10px !important;
}
.login-card{
  padding:24px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow: 0 8px 24px rgba(0,0,0,.06); background:#ffffff !important;
}
.hero-wrap{ max-width: 560px; }
.logo-card{
  display:inline-block; background:#fff; padding:14px; border-radius:18px;
  box-shadow: 0 6px 18px rgba(0,0,0,.06); border:1px solid #eee; margin-bottom:18px;
}
.logo-card img{ display:block; width:180px; height:auto; }
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
.btn-primary, .btn-ghost{
  display:inline-block; padding:10px 16px; border-radius:10px; text-decoration:none!important;
  border:1px solid #111; background:#fff; color:#111!important;
}
.cta-row{ display:flex; gap:12px; margin-top:8px; }
.footer{
  margin-top:40px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#444!important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# BACKGROUND
# =========================
def _bg_data_uri() -> Optional[str]:
    here = Path(__file__).parent
    for p in (here/"background.png", here/"assets"/"background.png"):
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{b64}"
    return None

_bg = _bg_data_uri()
if _bg:
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"]::before {{
      content:""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
      background: #f5f5f5 url('{_bg}') no-repeat center top;
      background-size: clamp(900px, 85vw, 1600px) auto; opacity: .50;
    }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# TEXTOS MULTILÍNGUE
# =========================
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

st.markdown('<div class="lang-row">', unsafe_allow_html=True)
lang_toggle = st.toggle("English", value=(st.session_state.lang=="en"), key="lang_toggle")
st.markdown('</div>', unsafe_allow_html=True)
st.session_state.lang = "en" if lang_toggle else "pt"

TXT = {
  "pt": {
    "eyebrow":"Plataforma OGMP 2.0 – L5",
    "title":"PLATAFORMA DE MONITORAMENTO DE METANO POR SATÉLITE",
    "subtitle":"Detecção, quantificação e insights acionáveis a partir de dados multissatélite.",
    "bul1":"Detecção e priorização de eventos",
    "bul2":"Relatórios OGMP 2.0 e auditoria",
    "bul3":"Geoportal com mapas, KPIs e séries históricas",
    "cta_login":"Login","cta_about":"Saiba mais",
    "secure_access":"Acesso Seguro",
    "bad_credentials":"Usuário ou senha inválidos.",
    "must_change":"Você está usando senha provisória. Defina uma nova senha para continuar.",
    "change_ok":"Senha alterada com sucesso.",
    "change_fail":"Erro ao salvar a nova senha."
  },
  "en": {
    "eyebrow":"OGMP 2.0 Platform – L5",
    "title":"SATELLITE METHANE MONITORING PLATFORM",
    "subtitle":"Detection, quantification and actionable insights from multi-satellite data.",
    "bul1":"Event detection & prioritization",
    "bul2":"OGMP 2.0 reporting & audit",
    "bul3":"Geoportal with maps, KPIs and time series",
    "cta_login":"Login","cta_about":"Learn more",
    "secure_access":"Secure Access",
    "bad_credentials":"Invalid username or password.",
    "must_change":"You are using a temporary password. Please set a new one to proceed.",
    "change_ok":"Password updated successfully.",
    "change_fail":"Failed to save new password."
  }
}
t = TXT[st.session_state.lang]

# =========================
# USERS.JSON (LOCAL OU GITHUB)
# =========================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_FILE_PATH = os.getenv("GITHUB_FILE_PATH", "users.json")

def gh_headers():
    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

def load_users():
    if GITHUB_TOKEN and GITHUB_REPO:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        r = requests.get(url, headers=gh_headers(), timeout=15)
        if r.status_code == 200:
            data = r.json()
            return json.loads(base64.b64decode(data["content"]).decode()), data["sha"]
    # fallback local
    p = Path(GITHUB_FILE_PATH)
    if not p.exists():
        p.write_text(json.dumps({"users":{}}, indent=2), encoding="utf-8")
    return json.loads(p.read_text("utf-8")), None

def save_users(cfg, msg, sha):
    data_b64 = base64.b64encode(json.dumps(cfg, indent=2).encode()).decode()
    if GITHUB_TOKEN and GITHUB_REPO:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        payload = {"message": msg, "content": data_b64}
        if sha: payload["sha"] = sha
        r = requests.put(url, headers=gh_headers(), json=payload, timeout=15)
        return r.status_code in (200,201)
    else:
        Path(GITHUB_FILE_PATH).write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return True

def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def check_password(p, h): return bcrypt.checkpw(p.encode(), h.encode())

# =========================
# LOGIN UI
# =========================
left, right = st.columns([1.2,1])
with left:
    st.markdown("<div class='hero-wrap'>", unsafe_allow_html=True)
    for cand in ("dapatlas.png","logo.png","logomavipe.jpeg"):
        if Path(cand).exists():
            st.markdown("<div class='logo-card'>", unsafe_allow_html=True)
            st.image(Image.open(cand), width=180)
            st.markdown("</div>", unsafe_allow_html=True)
            break
    st.markdown(f"<div class='hero-eyebrow'>{t['eyebrow']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-title'>{t['title']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-sub'>{t['subtitle']}</div>", unsafe_allow_html=True)
    st.markdown(f"<ul class='hero-bullets'><li>{t['bul1']}</li><li>{t['bul2']}</li><li>{t['bul3']}</li></ul>", unsafe_allow_html=True)

with right:
    st.markdown(f"<div class='login-card'><div class='login-title'>{t['secure_access']}</div>", unsafe_allow_html=True)
    cfg, cfg_sha = load_users()
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    login_btn = st.button("Entrar")
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# AUTENTICAÇÃO
# =========================
if login_btn:
    user = cfg.get("users", {}).get(u)
    if not user or not check_password(p, user["password"]):
        st.error(t["bad_credentials"])
    else:
        st.session_state["user"] = u
        st.session_state["must_change"] = user.get("must_change", False)
        st.experimental_rerun()

# =========================
# TROCA OBRIGATÓRIA DE SENHA
# =========================
if "user" in st.session_state and st.session_state.get("must_change"):
    st.warning(t["must_change"])
    with st.form("pwdchange"):
        old = st.text_input("Senha atual", type="password")
        new1 = st.text_input("Nova senha", type="password")
        new2 = st.text_input("Confirme a nova senha", type="password")
        ok = st.form_submit_button("Salvar nova senha")
    if ok:
        rec = cfg["users"][st.session_state["user"]]
        if check_password(old, rec["password"]) and new1 == new2 and len(new1) >= 8:
            rec["password"] = hash_password(new1)
            rec["must_change"] = False
            if save_users(cfg, f"chore(auth): password change for {st.session_state['user']}", cfg_sha):
                st.success(t["change_ok"])
                st.session_state["must_change"] = False
                st.experimental_rerun()
        else:
            st.error(t["change_fail"])

# =========================
# ÁREA AUTENTICADA
# =========================
if "user" in st.session_state and not st.session_state.get("must_change", False):
    st.sidebar.success(f"Logado como: {st.session_state['user']}")
    # Aqui você pode adicionar os links para as páginas da sua plataforma:
    for path, label, icon in [
        ("pages/2_Geoportal.py", "Geoportal", "🗺️"),
        ("pages/4_Agendamento_de_Imagens.py", "Agendamento de Imagens", "🗓️"),
        ("pages/3_Relatorio_OGMP_2_0.py", "Relatórios OGMP 2.0", "📄"),
        ("pages/1_Estatisticas_Gerais.py", "Estatísticas", "📊")
    ]:
        if Path(path).exists():
            st.sidebar.page_link(path, label=label, icon=icon)
    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.experimental_rerun()

# =========================
# FOOTER
# =========================
st.markdown("""
<div class="footer">
  DAP ATLAS · Ambiente: Produção · <a href="mailto:support@dapsistemas.com">Suporte</a>
</div>
""", unsafe_allow_html=True)

