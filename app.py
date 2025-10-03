# -*- coding: utf-8 -*-
import os
import json
import base64
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import bcrypt
import requests
import streamlit as st
from PIL import Image
from dotenv import load_dotenv

# =========================
# CONFIGURAÇÃO INICIAL
# =========================
st.set_page_config(
    page_title="Plataforma OGMP 2.0 - L5",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
load_dotenv()

# =========================
# VARIÁVEIS DE AMBIENTE (SECRETS)
# =========================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO_USERS = os.getenv("REPO_USERS", "")               # ex: dapsat100-star/new11
REPO_CRONOGRAMA = os.getenv("REPO_CRONOGRAMA", "")     # ex: dapsat100-star/cronograma
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GH_DATA_ROOT = os.getenv("GH_DATA_ROOT", "data/validado")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
    "Accept": "application/vnd.github+json",
}

# =========================
# CSS / LAYOUT
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
  box-shadow: 0 6px 18px rgba(0,0,0,.06); border:1px solid #eee; margin-bottom:18px;
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

# ===== Fundo com imagem (background.png na raiz ou /assets) =====
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
      content:"";
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      background: #f5f5f5 url('{_bg}') no-repeat center top;
      background-size: clamp(900px, 85vw, 1600px) auto; opacity: .5;
      filter: contrast(103%) brightness(101%);
    }}
    .block-container, [data-testid="stSidebar"], header, footer {{
      position: relative; z-index: 1;
    }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# FUNÇÕES GITHUB (JSON)
# =========================
def github_load_json(repo: str, path: str) -> Tuple[Dict[str, Any], Optional[str]]:
    if not (GITHUB_TOKEN and repo):
        return {}, None
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content), data.get("sha")
    elif r.status_code == 404:
        return {}, None
    else:
        st.error(f"Erro GitHub {r.status_code} ao ler `{repo}/{path}`.")
        st.code(r.text)
    return {}, None

def github_save_json(repo: str, path: str, content: dict, message: str, sha: Optional[str]) -> bool:
    if not (GITHUB_TOKEN and repo):
        st.error("GITHUB_TOKEN ou repositório não configurado.")
        return False
    payload = {
        "message": message,
        "content": base64.b64encode(json.dumps(content, indent=2).encode()).decode(),
        "branch": GITHUB_BRANCH
    }
    if sha:
        payload["sha"] = sha
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    r = requests.put(url, headers=HEADERS, json=payload, timeout=20)
    return r.status_code in (200, 201)

# =========================
# AUTENTICAÇÃO
# =========================
USERS_FILE = "users.json"

def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

# ===== HERO + LOGIN =====
left, right = st.columns([1.2, 1], gap="large")

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

# ===== PROCESSA LOGIN =====
if login_btn:
    users_cfg, users_sha = github_load_json(REPO_USERS, USERS_FILE)
    user_rec = users_cfg.get("users", {}).get(username or "")
    if not user_rec or not check_password(password, user_rec["password"]):
        st.error("Usuário ou senha inválidos.")
    else:
        st.session_state["user"] = username
        st.session_state["users_cfg"] = users_cfg
        st.session_state["users_sha"] = users_sha
        st.rerun()

# =========================
# TROCA OBRIGATÓRIA DE SENHA
# =========================
if "user" in st.session_state:
    users_cfg, users_sha = github_load_json(REPO_USERS, USERS_FILE)
    st.session_state["users_cfg"] = users_cfg
    st.session_state["users_sha"] = users_sha

    rec = users_cfg.get("users", {}).get(st.session_state["user"], {})
    if rec.get("must_change", False):
        st.warning("Você está usando senha provisória. Defina uma **nova senha** para continuar.")
        with st.form("form_change_pwd", clear_on_submit=False):
            old = st.text_input("Senha atual", type="password")
            new1 = st.text_input("Nova senha", type="password")
            new2 = st.text_input("Confirme a nova senha", type="password")
            sub = st.form_submit_button("Salvar nova senha")

        if sub:
            erros = []
            if not check_password(old, rec.get("password","")):
                erros.append("Senha atual incorreta.")
            if new1 != new2:
                erros.append("A nova senha e a confirmação não conferem.")
            if len(new1) < 8:
                erros.append("A nova senha deve ter pelo menos 8 caracteres.")
            if erros:
                for e in erros: st.error(f"• {e}")
            else:
                rec["password"] = hash_password(new1)
                rec["must_change"] = False
                ok = github_save_json(REPO_USERS, USERS_FILE, users_cfg,
                                      f"chore(auth): password change for {st.session_state['user']}",
                                      users_sha)
                if ok:
                    st.success("Senha alterada com sucesso ✅")
                    st.rerun()
                else:
                    st.error("Falha ao salvar a nova senha no GitHub.")

# =========================
# ÁREA AUTENTICADA
# =========================
if "user" in st.session_state:
    rec = st.session_state.get("users_cfg", {}).get("users", {}).get(st.session_state["user"], {})
    if rec.get("must_change", False) is True:
        st.stop()

    st.sidebar.success(f"Logado como: {st.session_state['user']}")
    st.sidebar.markdown("## 📁 Módulos")

    for path, label, icon in [
        ("pages/2_Geoportal.py", "Geoportal", "🗺️"),
        ("pages/4_Agendamento_de_Imagens.py", "Agendamentos", "🗓️"),
        ("pages/3_Relatorio_OGMP_2_0.py", "Relatórios", "📄"),
        ("pages/1_Estatisticas_Gerais.py", "Estatísticas", "📊"),
    ]:
        if Path(path).exists():
            st.sidebar.page_link(path, label=label, icon=icon)

    # ===== Redireciona automaticamente para a primeira página disponível =====
    def _first_existing(*paths: str) -> Optional[str]:
        for p in paths:
            if Path(p).exists():
                return p
        return None

    if "redirected_once" not in st.session_state:
        st.session_state["redirected_once"] = False

    if not st.session_state["redirected_once"]:
        target = _first_existing(
            "pages/2_Geoportal.py",
            "pages/4_Agendamento_de_Imagens.py",
            "pages/3_Relatorio_OGMP_2_0.py",
            "pages/1_Estatisticas_Gerais.py",
        )
        if target:
            st.session_state["redirected_once"] = True
            try:
                st.switch_page(target)
            except Exception:
                st.info("Use os atalhos na sidebar para abrir os módulos.")

    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()

    st.success("✅ Login realizado com sucesso.")
    st.write("Aqui você pode integrar os módulos do SaaS.")

# =========================
# FOOTER
# =========================
st.markdown("""
<div style="margin-top:40px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#444;">
  DAP ATLAS · Ambiente: Produção · <a href="mailto:support@dapsistemas.com">Suporte</a>
</div>
""", unsafe_allow_html=True)
