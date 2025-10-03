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
REPO_USERS = os.getenv("REPO_USERS")               # dapsat100-star/new11
REPO_CRONOGRAMA = os.getenv("REPO_CRONOGRAMA")     # dapsat100-star/cronograma
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GH_DATA_ROOT = os.getenv("GH_DATA_ROOT", "data/validado")

HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

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
.block-container{ padding-top: .5rem !important; }
* { color:#111 !important; }
.login-card{
  padding:24px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow:0 8px 24px rgba(0,0,0,.06); background:#fff;
}
.hero-title{font-size:44px; font-weight:900; letter-spacing:-0.02em;}
.hero-sub{font-size:16px; color:#222; max-width:56ch;}
</style>
""", unsafe_allow_html=True)

# =========================
# FUNÇÕES GITHUB
# =========================
def github_load_json(repo: str, path: str) -> Tuple[Dict[str, Any], str | None]:
    """Lê um arquivo JSON de um repositório GitHub"""
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
    """Salva um JSON de volta no GitHub (commit automático)"""
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
# LOGIN - USERS.JSON (REPO_USERS)
# =========================
USERS_FILE = "users.json"

def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def load_users():
    return github_load_json(REPO_USERS, USERS_FILE)

def save_users(data, message, sha):
    return github_save_json(REPO_USERS, USERS_FILE, data, message, sha)

# =========================
# HERO SECTION + LOGIN FORM
# =========================
left, right = st.columns([1.2, 1])

with left:
    st.markdown("<div class='hero-title'>Plataforma de Monitoramento OGMP 2.0</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-sub'>Detecção, quantificação e relatórios automatizados de metano com dados multissatélite.</div>", unsafe_allow_html=True)
    for cand in ("dapatlas.png","logo.png","logomavipe.jpeg"):
        if Path(cand).exists():
            st.image(Image.open(cand), width=180)
            break

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
    users_cfg, users_sha = load_users()
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
# TROCA OBRIGATÓRIA DE SENHA
# =========================
if "user" in st.session_state and st.session_state.get("must_change"):
    st.warning("Você está usando senha provisória. Defina uma nova senha para continuar.")
    with st.form("change_pwd"):
        old = st.text_input("Senha atual", type="password")
        new1 = st.text_input("Nova senha", type="password")
        new2 = st.text_input("Repita a nova senha", type="password")
        submitted = st.form_submit_button("Salvar nova senha")
    if submitted:
        rec = st.session_state["users_cfg"]["users"][st.session_state["user"]]
        if check_password(old, rec["password"]) and new1 == new2 and len(new1) >= 8:
            rec["password"] = hash_password(new1)
            rec["must_change"] = False
            if save_users(st.session_state["users_cfg"], f"Password change for {st.session_state['user']}", st.session_state["users_sha"]):
                st.success("Senha alterada com sucesso ✅")
                st.session_state["must_change"] = False
                st.experimental_rerun()
        else:
            st.error("Erro ao validar a troca de senha.")

# =========================
# ÁREA AUTENTICADA
# =========================
if "user" in st.session_state and not st.session_state.get("must_change", False):
    st.sidebar.success(f"Logado como: {st.session_state['user']}")
    st.sidebar.markdown("## 📁 Módulos")
    # Páginas internas (caso existam)
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
    st.write("Aqui você pode integrar os módulos de agendamento, dashboards, etc.")

    # Exemplo: ler arquivo do repositório CRONOGRAMA
    st.markdown("### 📊 Exemplo de leitura de arquivo do repositório cronograma")
    example_file = f"{GH_DATA_ROOT}/agenda.xlsx"
    data, sha = github_load_json(REPO_CRONOGRAMA, example_file)
    if data:
        st.info(f"Arquivo `{example_file}` encontrado no repositório {REPO_CRONOGRAMA}")
    else:
        st.warning(f"Arquivo `{example_file}` não encontrado no repositório {REPO_CRONOGRAMA}")

# =========================
# FOOTER
# =========================
st.markdown("""
<div style="margin-top:40px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#444;">
  DAP ATLAS · Ambiente: Produção · <a href="mailto:support@dapsistemas.com">Suporte</a>
</div>
""", unsafe_allow_html=True)
