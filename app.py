# -*- coding: utf-8 -*-
# app.py – Login + i18n com bandeiras (mesma aba) + background + troca de senha (users.json no GitHub)
# Suporta REPO com subpasta (ex.: "owner/repo/subpasta") e segredos via secrets.toml OU variáveis de ambiente.

import os
import json
import base64
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

import bcrypt
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

# =============================================================================
# Segredos (compatível com secrets.toml E variáveis de ambiente)
# =============================================================================
load_dotenv()  # permite ler variáveis do .env em dev local

def get_secret(key: str, default: str = "") -> str:
    """
    Lê segredos de forma tolerante:
    - tenta st.secrets (se .streamlit/secrets.toml existir)
    - senão, usa variável de ambiente (KEY em MAIÚSCULAS)
    """
    try:
        return st.secrets.get(key, default)
    except Exception:
        return os.getenv(key.upper(), default)

# =============================================================================
# Config inicial
# =============================================================================
st.set_page_config(
    page_title="Plataforma OGMP 2.0",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# Util: data-uri para imagens locais (bandeiras e background)
# =============================================================================
def _img_b64(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    mime = "image/svg+xml" if p.suffix.lower() == ".svg" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")

def _bg_data_uri() -> Optional[str]:
    here = Path(__file__).parent
    for p in (here / "background.png", here / "assets" / "background.png"):
        if p.exists():
            return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")
    return None

# =============================================================================
# Idioma (PT/EN)
# =============================================================================
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

qs_lang = st.query_params.get("lang")
if qs_lang:
    val = (qs_lang or "").lower()
    if val in ("pt", "en"):
        st.session_state.lang = val

is_pt = (st.session_state.lang == "pt")

TXT = {
    "pt": {
        "eyebrow": "OGMP 2.0 – L5",
        "title": "PLATAFORMA DE MONITORAMENTO DE METANO POR SATÉLITE",
        "subtitle": "Detecção, quantificação e relatórios automatizados de metano com dados multissatélite.",
        "bul1": "Detecção e priorização de eventos",
        "bul2": "Relatórios OGMP 2.0 e auditoria",
        "bul3": "Geoportal com mapas e séries históricas",
        "secure_access": "Acesso Seguro",
        "username": "Usuário",
        "password": "Senha",
        "signin": "Entrar",
        "forgot": "Esqueci minha senha",
        "forgot_msg": "Se você esqueceu sua senha, fale com o suporte para redefinição temporária.",
        "bad_credentials": "Usuário ou senha inválidos.",
        "confidential": "Acesso restrito. Conteúdo confidencial.",
        "logged_as": "Logado como",
        "modules": "Módulos",
        "login_ok": "Login realizado com sucesso. Bem-vindo!",
        "must_change": "Você está usando senha provisória. Defina uma nova senha para continuar.",
        "old_pwd": "Senha atual",
        "new_pwd": "Nova senha",
        "repeat_pwd": "Repita a nova senha",
        "save_pwd": "Salvar nova senha",
        "pwd_changed": "Senha alterada com sucesso ✅",
        "pwd_change_error": "Erro ao validar a troca de senha.",
        "cta_login": "Login",
        "cta_about": "Saiba mais",
        "about_link": "https://dapsat.com/",
        "support": "Suporte",
        "privacy": "Privacidade",
        "production": "Produção",
    },
    "en": {
        "eyebrow": "OGMP 2.0 – L5",
        "title": "SATELLITE METHANE MONITORING PLATFORM",
        "subtitle": "Detection, quantification and automated reporting from multi-satellite data.",
        "bul1": "Event detection & prioritization",
        "bul2": "OGMP 2.0 reporting & audit",
        "bul3": "Geoportal with maps & time series",
        "secure_access": "Secure Access",
        "username": "Username",
        "password": "Password",
        "signin": "Sign in",
        "forgot": "Forgot my password",
        "forgot_msg": "If you forgot your password, please contact support for a temporary reset.",
        "bad_credentials": "Invalid username or password.",
        "confidential": "Restricted access. Confidential content.",
        "logged_as": "Signed in as",
        "modules": "Modules",
        "login_ok": "Signed in successfully. Welcome!",
        "must_change": "You are using a temporary password. Set a new one to continue.",
        "old_pwd": "Current password",
        "new_pwd": "New password",
        "repeat_pwd": "Repeat the new password",
        "save_pwd": "Save new password",
        "pwd_changed": "Password changed successfully ✅",
        "pwd_change_error": "Could not validate password change.",
        "cta_login": "Login",
        "cta_about": "Learn more",
        "about_link": "https://dapsat.com/",
        "support": "Support",
        "privacy": "Privacy",
        "production": "Production",
    },
}
t = TXT["pt" if is_pt else "en"]

# =============================================================================
# CSS global + Background (com _bg dinâmico) + glass effect
# =============================================================================
_bg = _bg_data_uri()

st.markdown(
    f"""
<style>
/* Oculta cabeçalhos nativos */
header[data-testid="stHeader"]{{display:none!important;}}
div[data-testid="stToolbar"]{{display:none!important;}}
#MainMenu{{visibility:hidden;}}
footer{{visibility:hidden;}}
[data-testid="stSidebarNav"]{{display:none!important;}}
div[data-testid="collapsedControl"]{{display:block!important;}}

/* Fundo com imagem dinâmica se existir */
[data-testid="stAppViewContainer"]::before {{
  content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
  background: #f5f5f5 {'url(' + _bg + ')' if _bg else 'none'} no-repeat center top;
  background-size: clamp(900px, 85vw, 1600px) auto; opacity:.50;
  filter: contrast(103%) brightness(101%);
}}
.block-container, [data-testid="stSidebar"], header, footer {{
  position:relative; z-index:1;
}}

/* Card de login com glass effect */
.login-card{{
  padding:24px; border:1px solid rgba(231,231,231,.8); border-radius:16px;
  background: rgba(255,255,255,.55);
  box-shadow:0 8px 24px rgba(0,0,0,.06);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}}

/* Tipografia & botões do hero */
.hero-title{{ font-size:44px; line-height:1.05; font-weight:900; letter-spacing:-0.02em; margin:8px 0 10px 0; }}
.hero-sub{{ font-size:16px; color:#222; max-width:56ch; }}
.hero-bullets li{{ margin:6px 0; }}
.btn{{ display:inline-block; padding:10px 16px; border-radius:10px; text-decoration:none!important; }}
.btn-primary{{ border:1px solid #111; background:#fff; color:#111; }}
.btn-ghost{{ border:1px solid #e5e7eb; background:#fff; color:#111; }}

/* 👻 Patch: remove o retângulo branco fantasma do autofoco inicial */
section[data-testid="stTextInputRoot"] > div:empty,
div[data-testid="stTextInput"] > div:empty {{
  display: none !important;
}}
input:focus {{
  outline: none !important;
  box-shadow: none !important;
}}

/* ✨ Inputs com fundo cinza translúcido + foco suave */
[data-testid="stTextInput"] input {{
  background: rgba(240,240,240,.6) !important;
  border: 1px solid #ddd !important;
  border-radius: 8px !important;
  padding: 8px 10px !important;
  font-size: 14px !important;
  transition: background .2s, box-shadow .2s;
}}
[data-testid="stTextInput"] input:focus {{
  background: rgba(255,255,255,.75) !important;
  box-shadow: 0 0 0 2px rgba(0,0,0,.08) !important;
  outline: none !important;
}}

/* Pílula de idioma (bandeiras) */
.lang-pill {{
  position: fixed; top: 14px; left: 14px; z-index: 9999;
  display: inline-flex; align-items: center; gap: 10px;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 999px;
  padding: 6px 10px; box-shadow: 0 8px 20px rgba(0,0,0,.08);
}}
.lang-pill a {{
  display: inline-block; width: 26px; height: 20px;
  background-size: cover; background-position: center;
  border-radius: 4px; opacity: .85; transition: opacity .15s, outline-color .15s;
  outline: 2px solid transparent; outline-offset: 2px;
}}
.lang-pill a:hover {{ opacity: 1; }}
.lang-pill a.active {{ outline-color: #1f6feb; opacity: 1; }}
.lang-pill .divider {{
  width: 1px; height: 16px; background: #e5e7eb; display: inline-block;
}}
</style>
""",
    unsafe_allow_html=True,
)

# =============================================================================
# Pílula de idioma (sem abrir nova aba)
# =============================================================================
BR = _img_b64("br.svg")
GB = _img_b64("gb.svg")
st.markdown(
    f"""
<div class="lang-pill">
  <a href="?lang=pt" target="_self" class="{'active' if is_pt else ''}"
     style="background-image: url('{BR}');" title="Português"></a>
  <span class="divider"></span>
  <a href="?lang=en" target="_self" class="{'' if is_pt else 'active'}"
     style="background-image: url('{GB}');" title="English"></a>
</div>
""",
    unsafe_allow_html=True,
)

# =============================================================================
# GitHub helpers – users.json (SUPORTA subpasta em REPO)
# =============================================================================
GITHUB_TOKEN      = get_secret("github_token", "")
REPO_USERS        = get_secret("repo_users", "")            # ex.: "owner/repo" OU "owner/repo/subpasta"
REPO_CRONOGRAMA   = get_secret("REPO_CRONOGRAMA", "")       # se usar outro repo p/ dados
GITHUB_BRANCH     = get_secret("github_branch", "main")
GH_DATA_ROOT      = get_secret("GH_DATA_ROOT", "data/validado")
USERS_FILE        = "new11/users.json"


HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

def _split_repo_and_base(repo: str) -> tuple[str, str]:
    """
    Permite usar:
    - "owner/repo"               → sem subpasta
    - "owner/repo/sub/dir"       → com subpasta (base = "sub/dir")
    """
    parts = repo.split("/")
    if len(parts) < 2:
        return repo, ""
    owner_repo = "/".join(parts[:2])
    base = "/".join(parts[2:])  # "" se não houver subpasta
    return owner_repo, base

def _gh_open_json(repo: str, path: str) -> Tuple[Dict[str, Any], Optional[str]]:
    if not repo:
        return {}, None
    owner_repo, base = _split_repo_and_base(repo)
    full_path = f"{base}/{path}" if base else path
    url = f"https://api.github.com/repos/{owner_repo}/contents/{full_path}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code == 200:
        payload = r.json()
        content = base64.b64decode(payload["content"]).decode("utf-8")
        return json.loads(content), payload.get("sha")
    # Diagnóstico não intrusivo
    try:
        st.warning(f"Falha ao acessar {full_path} em {owner_repo} (HTTP {r.status_code})")
    except Exception:
        pass
    return {}, None

def _gh_save_json(repo: str, path: str, content: dict, message: str, sha: Optional[str]) -> bool:
    if not repo:
        return False
    owner_repo, base = _split_repo_and_base(repo)
    full_path = f"{base}/{path}" if base else path
    url = f"https://api.github.com/repos/{owner_repo}/contents/{full_path}"
    payload = {
        "message": message,
        "content": base64.b64encode(json.dumps(content, indent=2).encode()).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    ok = r.status_code in (200, 201)
    if not ok:
        try:
            st.error(f"Falha ao salvar {full_path} em {owner_repo} (HTTP {r.status_code})")
        except Exception:
            pass
    return ok

def load_users():
    return _gh_open_json(REPO_USERS, USERS_FILE)

def save_users(data, message, sha):
    return _gh_save_json(REPO_USERS, USERS_FILE, data, message, sha)

# =============================================================================
# Layout principal (hero + login)
# =============================================================================
left, right = st.columns([1.15, 1], gap="large")

with left:
    st.caption(t["eyebrow"])
    st.markdown(f"<div class='hero-title'>{t['title']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-sub'>{t['subtitle']}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <ul class='hero-bullets'>
          <li>{t['bul1']}</li>
          <li>{t['bul2']}</li>
          <li>{t['bul3']}</li>
        </ul>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<a class='btn btn-primary' href='#login'>{t['cta_login']}</a>&nbsp;"
        f"<a class='btn btn-ghost' href='{t['about_link']}' target='_blank' rel='noopener noreferrer'>{t['cta_about']}</a>",
        unsafe_allow_html=True,
    )

with right:
    st.markdown("<div id='login' class='login-card'>", unsafe_allow_html=True)
    st.subheader(t["secure_access"])
    username = st.text_input(t["username"])
    password = st.text_input(t["password"], type="password")
    c1, c2 = st.columns([1, 1])
    login_btn = c1.button(t["signin"])
    if c2.button(t["forgot"]):
        st.info(t["forgot_msg"])
    st.caption(t["confidential"])
    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# Autenticação
# =============================================================================
if login_btn:
    users_cfg, users_sha = load_users()
    user_rec = users_cfg.get("users", {}).get(username)
    if not user_rec or not bcrypt.checkpw(password.encode(), user_rec.get("password", "").encode()):
        st.error(t["bad_credentials"])
    else:
        st.session_state["user"] = username
        st.session_state["name"] = user_rec.get("name", username)
        st.session_state["must_change"] = bool(user_rec.get("must_change", False))
        st.session_state["users_sha"] = users_sha
        st.session_state["users_cfg"] = users_cfg
        st.session_state["authentication_status"] = True
        st.toast(t["login_ok"], icon="✅")
        st.rerun()

# =============================================================================
# Troca obrigatória de senha (primeiro acesso)
# =============================================================================
if st.session_state.get("user") and st.session_state.get("must_change"):
    st.warning(t["must_change"])
    with st.form("change_pwd"):
        old = st.text_input(t["old_pwd"], type="password")
        new1 = st.text_input(t["new_pwd"], type="password")
        new2 = st.text_input(t["repeat_pwd"], type="password")
        submitted = st.form_submit_button(t["save_pwd"])
    if submitted:
        rec = st.session_state["users_cfg"]["users"][st.session_state["user"]]
        if bcrypt.checkpw(old.encode(), rec.get("password", "").encode()) and new1 == new2 and len(new1) >= 8:
            rec["password"] = bcrypt.hashpw(new1.encode(), bcrypt.gensalt()).decode()
            rec["must_change"] = False
            if save_users(
                st.session_state["users_cfg"],
                f"Password change for {st.session_state['user']}",
                st.session_state["users_sha"],
            ):
                st.success(t["pwd_changed"])
                st.session_state["must_change"] = False
                st.rerun()
        else:
            st.error(t["pwd_change_error"])

# =============================================================================
# Área autenticada: sidebar + redirecionamento inicial
# =============================================================================
def _first_existing(*paths: str) -> Optional[str]:
    for p in paths:
        if Path(p).exists():
            return p
    return None

if st.session_state.get("authentication_status") and not st.session_state.get("must_change", False):
    st.sidebar.success(f"{t['logged_as']}: {st.session_state.get('name')}")
    st.sidebar.markdown(f"## {t['modules']}")

    GEO_PAGE       = _first_existing("pages/2_Geoportal.py", "2_Geoportal.py")
    AGENDA_PAGE    = _first_existing("pages/4_Agendamento_de_Imagens.py", "4_Agendamento_de_Imagens.py")
    RELATORIO_PAGE = _first_existing("pages/3_Relatorio_OGMP_2_0.py", "3_Relatorio_OGMP_2_0.py")
    ESTATS_PAGE    = _first_existing("pages/1_Estatisticas_Gerais.py", "1_Estatisticas_Gerais.py")

    if GEO_PAGE:       st.sidebar.page_link(GEO_PAGE, label="🗺️ Geoportal")
    if AGENDA_PAGE:    st.sidebar.page_link(AGENDA_PAGE, label="🗓️ Agendamentos")
    if RELATORIO_PAGE: st.sidebar.page_link(RELATORIO_PAGE, label="📄 Relatório OGMP 2.0")
    if ESTATS_PAGE:    st.sidebar.page_link(ESTATS_PAGE, label="📊 Estatísticas")

    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()

    # Redireciona na 1ª vez
    if not st.session_state.get("redirected_to_geoportal"):
        st.session_state["redirected_to_geoportal"] = True
        target = GEO_PAGE or AGENDA_PAGE or RELATORIO_PAGE or ESTATS_PAGE
        if target:
            try:
                st.switch_page(target)
            except Exception:
                pass

# =============================================================================
# Rodapé
# =============================================================================
APP_VERSION = os.getenv("APP_VERSION", "v1.0.0")
ENV_LABEL = t["production"]
st.markdown(
    f"""
<div style="margin-top:40px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#444;">
  DAP ATLAS · {APP_VERSION} · {ENV_LABEL} ·
  <a href="mailto:support@dapsistemas.com">{t["support"]}</a> ·
  <a href="https://example.com/privacidade" target="_blank">{t["privacy"]}</a>
</div>
""",
    unsafe_allow_html=True,
)
