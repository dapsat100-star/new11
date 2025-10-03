# -*- coding: utf-8 -*-
import os
import io
import json
import base64
import bcrypt
import smtplib
import secrets
import datetime as dt
from email.mime.text import MIMEText
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

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
# SECRETS/ENV
# =========================
# -> GitHub (onde está o users.json)
GITHUB_TOKEN = st.secrets.get("github_token") or os.getenv("GITHUB_TOKEN")
REPO_USERS   = st.secrets.get("repo_users")   or os.getenv("REPO_USERS")       # ex: dapsat100-star/new11
BRANCH       = st.secrets.get("github_branch", "main")

# -> E-mail (SMTP) para reset de senha
SMTP_HOST    = st.secrets.get("smtp_host")
SMTP_PORT    = int(st.secrets.get("smtp_port", 587))
SMTP_USER    = st.secrets.get("smtp_user")
SMTP_PASS    = st.secrets.get("smtp_pass")
SMTP_FROM    = st.secrets.get("smtp_from")        # ex: "no-reply@dapsat.com"
APP_BASE_URL = st.secrets.get("app_base_url")     # ex: "https://<seu-app>.streamlit.app/"

# headers GitHub
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

USERS_FILE = "users.json"
RESET_TTL_HOURS = 2  # validade do link de reset

# =========================
# i18n (telas de login/hero)
# =========================
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
    "signin":"Entrar",
    "forgot":"Esqueci minha senha",
    "confidential":"Acesso restrito. Conteúdo confidencial.",
    "bad_credentials":"Usuário ou senha inválidos.",
    "login_hint":"Por favor, faça login para continuar.",
    "support":"Suporte",
    "privacy":"Privacidade",
    "internal":"Uso interno",
    "reset_title":"Redefinir senha",
    "reset_intro":"Informe seu usuário ou e-mail para enviarmos um link de redefinição.",
    "send_link":"Enviar link",
    "reset_sent":"Se o usuário/e-mail existir, enviaremos um link (válido por {hrs}h).",
    "reset_via_link":"Redefinir senha via link",
    "new_pwd":"Nova senha",
    "new_pwd2":"Repita a nova senha",
    "save_new_pwd":"Salvar nova senha",
    "pwd_changed":"Senha alterada com sucesso. Faça login novamente.",
    "token_invalid":"Token inválido ou expirado. Solicite um novo link.",
    "signin_ok":"Login realizado com sucesso. Bem-vindo!",
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
    "signin":"Sign in",
    "forgot":"Forgot my password",
    "confidential":"Restricted access. Confidential content.",
    "bad_credentials":"Invalid username or password.",
    "login_hint":"Please sign in to continue.",
    "support":"Support",
    "privacy":"Privacy",
    "internal":"Internal use",
    "reset_title":"Reset password",
    "reset_intro":"Enter your username or e-mail and we’ll send you a reset link.",
    "send_link":"Send link",
    "reset_sent":"If the account exists, we have sent a link (valid for {hrs}h).",
    "reset_via_link":"Reset password via link",
    "new_pwd":"New password",
    "new_pwd2":"Repeat new password",
    "save_new_pwd":"Save new password",
    "pwd_changed":"Password changed. Please sign in.",
    "token_invalid":"Invalid or expired token. Please request a new link.",
    "signin_ok":"Signed in successfully. Welcome!",
  }
}

# idioma default no estado
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

# =========================
# BG (background.png -> base64)
# =========================
def _bg_data_uri():
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
      content:""; position: fixed; inset: 0; z-index: 0; pointer-events:none;
      background: #f5f5f5 url('{_bg}') no-repeat center top;
      background-size: clamp(900px, 85vw, 1600px) auto; opacity: .50;
      filter: contrast(103%) brightness(101%);
    }}
    .block-container, [data-testid="stSidebar"], header, footer {{ position:relative; z-index:1; }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# CSS base (hero + login)
# =========================
st.markdown("""
<style>
header[data-testid="stHeader"]{display:none!important;}
div[data-testid="stToolbar"]{display:none!important;}
#MainMenu{visibility:hidden;} footer{visibility:hidden;}
/* oculta menu multipágina nativo */
[data-testid="stSidebarNav"]{ display:none !important; }
div[data-testid="collapsedControl"]{ display:block !important; }

.block-container{ padding-top:.5rem !important; }
* { color:#111 !important; }
a { color:#111 !important; text-decoration: underline; }

/* Cartão de login */
.login-card{
  padding:24px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow: 0 8px 24px rgba(0,0,0,.06); background:#ffffff;
}
.login-title{ font-size:18px; margin:0 0 14px 0; font-weight:700; }

/* hero */
.hero-wrap{ max-width:560px; }
.hero-eyebrow{
  display:inline-block; font-size:12px; letter-spacing:.14em; text-transform:uppercase;
  padding:6px 12px; border:1px solid #cfcfcf; color:#222!important;
  border-radius:999px; background:#f7f7f7; margin:8px 0 14px 0;
}
.hero-title{
  font-size:44px; line-height:1.05; font-weight:900; letter-spacing:-0.02em; margin:8px 0 10px 0;
}
@media (min-width:1200px){ .hero-title{ font-size:48px; } }
.hero-sub{ font-size:16px; color:#222; max-width:56ch; margin:0 0 10px 0; }
.hero-bullets{ margin:8px 0 18px 18px; } .hero-bullets li{ margin:6px 0; }

/* Chip do idioma (🇧🇷 ◀︎ toggle ▶︎ 🇬🇧) */
#lang-chip {
  position: fixed; top: 12px; left: 12px; z-index: 2000;
  background:#fff; border:1px solid #e7e7e7; border-radius:999px;
  padding:6px 10px; box-shadow:0 6px 18px rgba(0,0,0,.08);
  display:flex; align-items:center; gap:8px; height:38px;
}
#lang-chip .stVerticalBlock, #lang-chip .stHorizontalBlock { margin:0!important; padding:0!important; }
#lang-chip [data-testid="stWidgetLabel"]{display:none!important;}
.lang-flag{ font-size:18px; line-height:1; }

/* Footer */
.footer{ margin-top:40px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#444!important; }
</style>
""", unsafe_allow_html=True)

# =========================
# Chip de Idioma (PT/EN)
# =========================
st.markdown('<div id="lang-chip">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([0.25, 0.9, 0.25], vertical_alignment="center")
with c1: st.markdown("<span class='lang-flag'>🇧🇷</span>", unsafe_allow_html=True)
with c2:
    is_en = st.toggle("", value=(st.session_state.lang == "en"),
                      key="__lang_toggle__", label_visibility="collapsed")
with c3: st.markdown("<span class='lang-flag'>🇬🇧</span>", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
st.session_state.lang = "en" if is_en else "pt"
t = TXT[st.session_state.lang]

# =========================
# GitHub utils
# =========================
def github_load_json(repo: str, path: str) -> Tuple[Dict[str, Any], Optional[str]]:
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={BRANCH}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content), data.get("sha")
    elif r.status_code == 404:
        return {}, None
    else:
        st.error(f"GitHub error {r.status_code}: {r.text}")
        return {}, None

def github_save_json(repo: str, path: str, content: dict, message: str, sha: Optional[str]) -> bool:
    payload = {
        "message": message,
        "content": base64.b64encode(json.dumps(content, indent=2).encode()).decode(),
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    r = requests.put(url, headers=HEADERS, json=payload, timeout=20)
    return r.status_code in (200, 201)

def load_users():  return github_load_json(REPO_USERS, USERS_FILE)
def save_users(cfg, msg, sha): return github_save_json(REPO_USERS, USERS_FILE, cfg, msg, sha)

# =========================
# Auth helpers
# =========================
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def check_password(plain: str, hashed: str) -> bool:
    try: return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception: return False

# =========================
# E-mail reset helpers
# =========================
def send_reset_email(to_email: str, username: str, token: str):
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, APP_BASE_URL]):
        st.warning("Warning: configure github_token and repo_users in secrets.")
        return False
    link = f"{APP_BASE_URL}?reset_token={token}&u={username}"
    subject = "Redefinição de senha – DAP ATLAS"
    body = f"""
Olá {username},

Recebemos um pedido para redefinir sua senha.
Clique no link abaixo para definir uma nova senha (válido por {RESET_TTL_HOURS} hora(s)):

{link}

Se você não solicitou, ignore este e-mail.

DAP ATLAS
"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_FROM, [to_email], msg.as_string())
        return True
    except Exception as e:
        st.error(f"Falha ao enviar e-mail: {e}")
        return False

def create_reset_token(cfg: dict, username: str) -> Optional[str]:
    users = cfg.get("users", {})
    rec = users.get(username)
    if not rec: return None
    token = secrets.token_urlsafe(32)
    exp = (dt.datetime.utcnow() + dt.timedelta(hours=RESET_TTL_HOURS)).isoformat() + "Z"
    rec["reset"] = {"token": token, "exp": exp}
    return token

def validate_reset_token(cfg: dict, username: str, token: str) -> bool:
    try:
        rec = cfg.get("users", {}).get(username)
        rst = rec.get("reset")
        if not rst: return False
        if rst.get("token") != token: return False
        exp = dt.datetime.fromisoformat(rst["exp"].replace("Z",""))
        return dt.datetime.utcnow() <= exp
    except Exception:
        return False

def clear_reset_token(cfg: dict, username: str):
    try:
        cfg["users"][username].pop("reset", None)
    except Exception:
        pass

# =========================
# HERO + LOGIN / RESET
# =========================
left, right = st.columns([1.15, 1], gap="large")

with left:
    st.markdown("<div class='hero-wrap'>", unsafe_allow_html=True)
    for cand in ("dapatlas.png","logo.png","logomavipe.jpeg"):
        if Path(cand).exists():
            st.image(Image.open(cand), width=180)
            break
    st.markdown(f"<div class='hero-eyebrow'>{t['eyebrow']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-title'>{t['title']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-sub'>{t['subtitle']}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<ul class='hero-bullets'><li>{t['bul1']}</li><li>{t['bul2']}</li><li>{t['bul3']}</li></ul>",
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown(f"<div class='login-card'><div class='login-title'>{t['secure']}</div>", unsafe_allow_html=True)

    # --- rota de reset via link: ?reset_token=...&u=...
    q = st.query_params
    if "reset_token" in q and "u" in q:
        token = q.get("reset_token")
        username_q = q.get("u")
        st.subheader(t["reset_via_link"])
        new1 = st.text_input(t["new_pwd"], type="password")
        new2 = st.text_input(t["new_pwd2"], type="password")
        if st.button(t["save_new_pwd"], type="primary"):
            cfg, sha = load_users()
            if cfg and validate_reset_token(cfg, username_q, token) and new1 == new2 and len(new1) >= 8:
                cfg["users"][username_q]["password"] = hash_password(new1)
                cfg["users"][username_q]["must_change"] = False
                clear_reset_token(cfg, username_q)
                if save_users(cfg, f"Password reset for {username_q}", sha):
                    st.success(t["pwd_changed"])
                    # limpa query string
                    st.query_params.clear()
                else:
                    st.error("Erro ao salvar nova senha.")
            else:
                st.error(t["token_invalid"])
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # --- formulário de login
    username = st.text_input(t["username"])
    password = st.text_input(t["password"], type="password")
    colA, colB = st.columns([1,1])
    with colA:
        login_btn = st.button(t["signin"], type="primary")
    with colB:
        forgot_btn = st.button(t["forgot"])

    st.caption(t["confidential"])
    st.markdown("</div>", unsafe_allow_html=True)

# ======= Ações =======
if forgot_btn:
    with st.form("reset_form"):
        st.subheader(t["reset_title"])
        st.write(t["reset_intro"])
        who = st.text_input(f"{t['username']}/e-mail")
        submit = st.form_submit_button(t["send_link"])
    if submit and who.strip():
        cfg, sha = load_users()
        # localizar por username OU email
        target_user = None
        for uname, rec in cfg.get("users", {}).items():
            if who.strip().lower() in (uname.lower(), str(rec.get("email","")).lower()):
                target_user = (uname, rec); break
        if target_user:
            uname, rec = target_user
            token = create_reset_token(cfg, uname)
            if token and save_users(cfg, f"Create reset token for {uname}", sha):
                ok = send_reset_email(rec.get("email") or who.strip(), uname, token)
                if ok:
                    st.success(t["reset_sent"].format(hrs=RESET_TTL_HOURS))
                else:
                    st.warning("Não foi possível enviar e-mail agora.")
            else:
                st.error("Falha ao gerar link. Tente novamente.")
        else:
            # resposta neutra por segurança
            st.success(t["reset_sent"].format(hrs=RESET_TTL_HOURS))

if login_btn:
    cfg, sha = load_users()
    user_rec = cfg.get("users", {}).get(username)
    if not user_rec or not check_password(password, user_rec["password"]):
        st.error(t["bad_credentials"])
    else:
        st.session_state["user"] = username
        st.session_state["must_change"] = user_rec.get("must_change", False)
        st.toast(t["signin_ok"], icon="✅")
        st.session_state["authentication_status"] = True
        st.session_state["name"] = user_rec.get("name") or username
        st.session_state["username"] = username
        # redireciona pro Geoportal (se existir)
        target = None
        for path in ("pages/2_Geoportal.py","2_Geoportal.py",
                     "pages/4_Agendamento_de_Imagens.py","4_Agendamento_de_Imagens.py"):
            if Path(path).exists(): target = path; break
        if target:
            try:
                st.switch_page(target)
            except Exception:
                st.success("Use os atalhos na sidebar para abrir os módulos.")

# =========================
# Footer
# =========================
APP_VERSION = os.getenv("APP_VERSION","v1.0.0")
ENV_LABEL = "Produção" if st.session_state.lang == "pt" else "Production"
st.markdown(f"""
<div class="footer">
  <div>DAP ATLAS · {APP_VERSION} · {ENV_LABEL}</div>
  <div>{t["internal"]} · <a href="mailto:support@dapsistemas.com">{t["support"]}</a> · 
       <a href="https://example.com/privacidade" target="_blank">{t["privacy"]}</a></div>
</div>
""", unsafe_allow_html=True)
