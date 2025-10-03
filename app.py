# -*- coding: utf-8 -*-
# app.py — Login + i18n + background + reset de senha c/ GitHub

import os
import io
import json
import time
import base64
import random
import string
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import bcrypt
import requests
import streamlit as st
from PIL import Image

# ============================================================================
# CONFIG INICIAL
# ============================================================================
st.set_page_config(
    page_title="Plataforma OGMP 2.0",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================================
# BACKGROUND (usa background.png ou assets/background.png)
# ============================================================================
def _bg_data_uri() -> Optional[str]:
    here = Path(__file__).parent
    for p in (here/"background.png", here/"assets"/"background.png"):
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{b64}"
    return None

_BG = _bg_data_uri()
st.markdown("""
<style>
/* esconde cromos do streamlit */
header[data-testid="stHeader"]{display:none!important;}
div[data-testid="stToolbar"]{display:none!important;}
#MainMenu, footer{visibility:hidden;}

/* container geral + background */
[data-testid="stAppViewContainer"]{ padding-top: 0 !important; }
.block-container{ padding-top: .5rem !important; }

/* aplica o background como pseudo-elemento, não desloca layout */
[data-testid="stAppViewContainer"]::before{
  content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
  background:#f5f5f5;
}
.block-container, [data-testid="stSidebar"], header, footer{ position:relative; z-index:1; }

/* cartão de login */
.login-card{
  padding:24px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow:0 8px 24px rgba(0,0,0,.06); background:#fff;
}

/* título hero */
.hero-title{
  font-size:44px; line-height:1.05; font-weight:900; letter-spacing:-0.02em;
  margin:8px 0 10px 0;
}
.hero-sub{ font-size:16px; color:#222; max-width:56ch; margin:0 0 10px 0; }

/* botões */
.btn, .btn-ghost{
  display:inline-block; padding:10px 16px; border-radius:10px; text-decoration:none!important;
}
.btn{ background:#111; color:#fff !important; border:1px solid #111; }
.btn-ghost{ background:#fff; color:#111 !important; border:1px solid #111; }

/* ---- LINGUA: barra compacta no topo-esquerdo ---- */
#langbar{
  position:fixed; top:14px; left:18px; z-index:1000;
  display:inline-flex; align-items:center; gap:8px;
  background:transparent; padding:0; border:0; box-shadow:none;
}
#langbar [data-testid="stHorizontalBlock"]{ display:inline-flex !important; gap:8px !important; }
#langbar [data-testid="column"]{ flex:0 0 auto !important; padding:0 !important; }

/* bandeirinhas */
#langbar .flag{ width:22px; height:22px; border-radius:2px; box-shadow:0 1px 2px rgba(0,0,0,.15); user-select:none; }

/* toggle compacto (sem label) */
#langbar [data-testid="stToggle"]{ transform:scale(.90); }
#langbar [data-testid="stToggle"] label p{ display:none !important; }

/* oculta o menu multipágina nativo da sidebar */
[data-testid="stSidebarNav"]{ display:none!important; }

/* melhora contraste do aviso */
.stAlert > div{ border:1px solid #f1e3a8; }
</style>
""", unsafe_allow_html=True)

# injeta a imagem de fundo se existir
if _BG:
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"]::before {{
            background: #f5f5f5 url('{_BG}') no-repeat center top;
            background-size: clamp(900px, 85vw, 1600px) auto;
            opacity: .55; filter: contrast(103%) brightness(101%);
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# I18N
# ============================================================================
BR_FLAG = None
GB_FLAG = None
for path in ("assets/flag-br.png", "flag-br.png"):
    p = Path(path)
    if p.exists():
        BR_FLAG = base64.b64encode(p.read_bytes()).decode("ascii")
for path in ("assets/flag-gb.png", "flag-gb.png", "assets/flag-uk.png", "flag-uk.png"):
    p = Path(path)
    if p.exists():
        GB_FLAG = base64.b64encode(p.read_bytes()).decode("ascii")

if "lang" not in st.session_state:
    st.session_state.lang = "pt"

st.markdown('<div id="langbar">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1,1,1])
with c1:
    st.markdown(
        f"<img class='flag' src='data:image/png;base64,{BR_FLAG}'/>" if BR_FLAG else "🇧🇷",
        unsafe_allow_html=True
    )
with c2:
    checked = (st.session_state.lang == "en")
    if st.toggle("English", value=checked, key="__lang__", label_visibility="collapsed"):
        st.session_state.lang = "en"
    else:
        st.session_state.lang = "pt"
with c3:
    st.markdown(
        f"<img class='flag' src='data:image/png;base64,{GB_FLAG}'/>" if GB_FLAG else "🇬🇧",
        unsafe_allow_html=True
    )
st.markdown('</div>', unsafe_allow_html=True)

TXT = {
  "pt": {
      "eyebrow":"OGMP 2.0 – L5",
      "title":"PLATAFORMA DE MONITORAMENTO DE METANO POR SATÉLITE",
      "subtitle":"Detecção, quantificação e relatórios automatizados com dados multissatélite.",
      "bul1":"Detecção e priorização de eventos",
      "bul2":"Relatórios OGMP 2.0 e auditoria",
      "bul3":"Geoportal com mapas e séries históricas",
      "secure":"Acesso Seguro",
      "username":"Usuário",
      "password":"Senha",
      "sign_in":"Entrar",
      "forgot":"Esqueci minha senha",
      "confidential":"Acesso restrito. Conteúdo confidencial.",
      "bad_credentials":"Usuário ou senha inválidos.",
      "login_hint":"Por favor, faça login para continuar.",
      "logged_as":"Logado como",
      "support":"Suporte",
      "privacy":"Privacidade",
      "internal_use":"Uso interno",
      "reset_ok":"Senha temporária gerada com sucesso. Use-a para entrar e troque em seguida:",
      "reset_err":"Não foi possível gerar a senha provisória.",
      "need_user":"Informe o usuário para recuperar a senha.",
      "new_pwd_title":"Definir nova senha (obrigatório)",
      "old_pwd":"Senha atual",
      "new_pwd":"Nova senha",
      "repeat_pwd":"Repita a nova senha",
      "save_pwd":"Salvar nova senha"
  },
  "en": {
      "eyebrow":"OGMP 2.0 – L5",
      "title":"SATELLITE METHANE MONITORING PLATFORM",
      "subtitle":"Detection, quantification and automated reporting from multi-satellite data.",
      "bul1":"Event detection & prioritization",
      "bul2":"OGMP 2.0 reporting & audit",
      "bul3":"Geoportal with maps & time series",
      "secure":"Secure Access",
      "username":"Username",
      "password":"Password",
      "sign_in":"Sign in",
      "forgot":"Forgot my password",
      "confidential":"Restricted access. Confidential content.",
      "bad_credentials":"Invalid username or password.",
      "login_hint":"Please sign in to continue.",
      "logged_as":"Signed in as",
      "support":"Support",
      "privacy":"Privacy",
      "internal_use":"Internal use",
      "reset_ok":"Temporary password created. Use it to sign in and then change it:",
      "reset_err":"Couldn’t issue a temporary password.",
      "need_user":"Type your username to recover the password.",
      "new_pwd_title":"Set a new password (required)",
      "old_pwd":"Current password",
      "new_pwd":"New password",
      "repeat_pwd":"Repeat new password",
      "save_pwd":"Save new password"
  }
}
t = TXT[st.session_state.lang]

# ============================================================================
# GITHUB HELPERS (users.json no repo_users)
# ============================================================================
def _gh_headers():
    headers = {"Accept": "application/vnd.github+json"}
    tok = st.secrets.get("github_token")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers

REPO_USERS = st.secrets.get("repo_users")            # "dapsat100-star/new11"
GITHUB_BRANCH = st.secrets.get("github_branch", "main")

def gh_get_json(repo: str, path: str) -> Tuple[Dict[str, Any], Optional[str]]:
    if not repo:
        st.warning("Warning: configure github_token and repo_users in secrets.")
        return {}, None
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=_gh_headers(), timeout=20)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content), data.get("sha")
    elif r.status_code == 404:
        return {}, None
    else:
        st.error(f"Erro GitHub: {r.status_code} - {r.text}")
        return {}, None

def gh_put_json(repo: str, path: str, obj: dict, message: str, sha: Optional[str]) -> bool:
    if not repo:
        return False
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(json.dumps(obj, indent=2, ensure_ascii=False).encode()).decode(),
        "branch": GITHUB_BRANCH
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), json=payload, timeout=30)
    return r.status_code in (200, 201)

USERS_FILE = "users.json"

def load_users():
    return gh_get_json(REPO_USERS, USERS_FILE)

def save_users(data, msg, sha):
    return gh_put_json(REPO_USERS, USERS_FILE, data, msg, sha)

def _hash(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def _check(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False

def _strong_temp_password(n: int = 12) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(random.SystemRandom().choice(chars) for _ in range(n))

# ============================================================================
# LAYOUT (hero à esquerda, login à direita)
# ============================================================================
left, right = st.columns([1.15, 1], gap="large")

with left:
    # logo (se existir qualquer arquivo esperado)
    for cand in ("dapatlas.png","dapatlas.jpeg","logo.png","logo.jpeg","logomavipe.jpeg"):
        if Path(cand).exists():
            st.image(Image.open(cand), width=180)
            break
    st.caption(t["eyebrow"])
    st.markdown(f"<div class='hero-title'>{t['title']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-sub'>{t['subtitle']}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <ul>
          <li>{t['bul1']}</li>
          <li>{t['bul2']}</li>
          <li>{t['bul3']}</li>
        </ul>
        """,
        unsafe_allow_html=True
    )

with right:
    st.markdown(f"<div class='login-card'><h3>{t['secure']}</h3>", unsafe_allow_html=True)
    username = st.text_input(t["username"])
    password = st.text_input(t["password"], type="password")
    cA, cB = st.columns([1,1])
    with cA:
        login_btn = st.button(t["sign_in"])
    with cB:
        forgot_btn = st.button(t["forgot"])
    st.caption(t["confidential"])
    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================================
# LOGIN FLOW
# ============================================================================
def _redirect_to_first_available():
    # tenta ir direto para o Geoportal; senão mostra links
    def _first_existing(*paths: str) -> Optional[str]:
        for p in paths:
            if Path(p).exists():
                return p
        return None
    GEO = _first_existing("pages/2_Geoportal.py", "2_Geoportal.py")
    AGEN = _first_existing("pages/4_Agendamento_de_Imagens.py", "4_Agendamento_de_Imagens.py")
    REL = _first_existing("pages/3_Relatorio_OGMP_2_0.py", "3_Relatorio_OGMP_2_0.py")
    EST = _first_existing("pages/1_Estatisticas_Gerais.py", "1_Estatisticas_Gerais.py")
    target = GEO or AGEN or REL or EST
    if target:
        try:
            st.switch_page(target)
        except Exception:
            st.success("Login OK! Use os atalhos abaixo para abrir os módulos.")
            if GEO: st.page_link(GEO, label="🗺️ Geoportal")
            if AGEN: st.page_link(AGEN, label="🗓️ Agendamento de Imagens")
            if REL: st.page_link(REL, label="📄 Relatório OGMP 2.0")
            if EST: st.page_link(EST, label="📊 Estatísticas")
            st.stop()

# faz login
if login_btn:
    users_cfg, users_sha = load_users()
    user_rec = users_cfg.get("users", {}).get(username)
    if not user_rec or not _check(password, user_rec.get("password","")):
        st.error(t["bad_credentials"])
    else:
        st.session_state["authentication_status"] = True
        st.session_state["name"] = user_rec.get("name") or username
        st.session_state["username"] = username
        st.session_state["must_change"] = bool(user_rec.get("must_change", False))
        st.session_state["users_cfg"] = users_cfg
        st.session_state["users_sha"] = users_sha
        if st.session_state["must_change"]:
            st.warning(t["new_pwd_title"])

# esqueci a senha → gera temporária e marca must_change
if forgot_btn:
    if not username:
        st.warning(t["need_user"])
    else:
        users_cfg, users_sha = load_users()
        users = users_cfg.get("users", {})
        if username in users:
            tmp = _strong_temp_password(12)
            users[username]["password"] = _hash(tmp)
            users[username]["must_change"] = True
            ok = save_users(users_cfg, f"password reset for {username}", users_sha)
            if ok:
                st.success(f"{t['reset_ok']}  \n`{tmp}`")
            else:
                st.error(t["reset_err"])
        else:
            st.error(t["bad_credentials"])

# troca obrigatória de senha
if st.session_state.get("authentication_status") and st.session_state.get("must_change"):
    with st.form("change_pwd"):
        st.subheader(t["new_pwd_title"])
        old = st.text_input(t["old_pwd"], type="password")
        new1 = st.text_input(t["new_pwd"], type="password")
        new2 = st.text_input(t["repeat_pwd"], type="password")
        sub = st.form_submit_button(t["save_pwd"])
    if sub:
        users_cfg = st.session_state["users_cfg"]
        users_sha = st.session_state["users_sha"]
        rec = users_cfg.get("users", {}).get(st.session_state["username"])
        if not rec:
            st.error(t["bad_credentials"])
        elif not _check(old, rec.get("password","")):
            st.error(t["bad_credentials"])
        elif new1 != new2 or len(new1) < 8:
            st.error("Nova senha inválida (mínimo 8 caracteres e ambas iguais).")
        else:
            rec["password"] = _hash(new1)
            rec["must_change"] = False
            if save_users(users_cfg, f"password change for {st.session_state['username']}", users_sha):
                st.success("Senha alterada com sucesso. ✅")
                st.session_state["must_change"] = False
                _redirect_to_first_available()
            else:
                st.error("Falha ao salvar no GitHub.")

# sessão autenticada (sem troca pendente) → redireciona
if st.session_state.get("authentication_status") and not st.session_state.get("must_change"):
    _redirect_to_first_available()

# rodapé
APP_VERSION = "v1.0.0"
ENV_LABEL = "Produção"
st.markdown(
    f"""
    <div style="margin-top:40px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#444;">
      DAP ATLAS · {APP_VERSION} · Ambiente: {ENV_LABEL} · 
      <a href="mailto:support@dapsistemas.com">{t['support']}</a> · 
      <a href="https://example.com/privacidade" target="_blank">{t['privacy']}</a>
    </div>
    """,
    unsafe_allow_html=True
)
