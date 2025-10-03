# -*- coding: utf-8 -*-
# app.py – Login + i18n com bandeiras + background + troca de senha (users.json no GitHub)

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
# Config inicial
# =============================================================================
st.set_page_config(
    page_title="Plataforma OGMP 2.0",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
load_dotenv()

# =============================================================================
# Util: data-uri para imagens locais
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
# CSS + Background
# =============================================================================
_bg = _bg_data_uri()

st.markdown(
    f"""
<style>
header[data-testid="stHeader"]{{display:none!important;}}
div[data-testid="stToolbar"]{{display:none!important;}}
#MainMenu{{visibility:hidden;}}
footer{{visibility:hidden;}}
[data-testid="stSidebarNav"]{{display:none!important;}}
div[data-testid="collapsedControl"]{{display:block!important;}}

[data-testid="stAppViewContainer"]::before {{
  content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
  background: #f5f5f5 {'url(' + _bg + ')' if _bg else 'none'} no-repeat center top;
  background-size: clamp(900px, 85vw, 1600px) auto; opacity:.50;
  filter: contrast(103%) brightness(101%);
}}
.block-container, [data-testid="stSidebar"], header, footer {{
  position:relative; z-index:1;
}}

/* Card de login */
.login-card {{
  position: relative;
  padding:24px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow:0 8px 24px rgba(0,0,0,.06); background:#fff;
}}

/* Badge “Acesso Seguro” dentro do card */
.login-badge {{
  position: absolute;
  top: 10px;
  right: 12px;
  padding: 6px 10px;
  border-radius: 10px;
  background: rgba(255,255,255,0.85);
  border: 1px solid #e5e7eb;
  color: #111;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  box-shadow: 0 6px 14px rgba(0,0,0,.06);
  backdrop-filter: blur(2px);
}}

.hero-title{{ font-size:44px; line-height:1.05; font-weight:900; letter-spacing:-0.02em; margin:8px 0 10px 0; }}
.hero-sub{{ font-size:16px; color:#222; max-width:56ch; }}
.hero-bullets li{{ margin:6px 0; }}
.btn{{ display:inline-block; padding:10px 16px; border-radius:10px; text-decoration:none!important; }}
.btn-primary{{ border:1px solid #111; background:#fff; color:#111; }}
.btn-ghost{{ border:1px solid #e5e7eb; background:#fff; color:#111; }}
</style>
""",
    unsafe_allow_html=True,
)

# =============================================================================
# Hero + Login
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
    # Badge no lugar do antigo título
    st.markdown(f"<div class='login-badge'>{t['secure_access']}</div>", unsafe_allow_html=True)
    username = st.text_input(t["username"])
    password = st.text_input(t["password"], type="password")
    c1, c2 = st.columns([1, 1])
    login_btn = c1.button(t["signin"])
    if c2.button(t["forgot"]):
        st.info(t["forgot_msg"])
    st.caption(t["confidential"])
    st.markdown("</div>", unsafe_allow_html=True)
