# -*- coding: utf-8 -*-
# app.py — Login + i18n + troca de senha + reset + redirecionamento + BG (fix CSS)

import os
import io
import json
import base64
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
# SECRETS (GitHub)
# ============================================================================
GITHUB_TOKEN   = st.secrets.get("github_token", "")
REPO_USERS     = st.secrets.get("repo_users", "")            # ex.: "dapsat100-star/new11"
GITHUB_BRANCH  = st.secrets.get("github_branch", "main")

HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

# ============================================================================
# BACKGROUND
# ============================================================================
def _bg_data_uri():
    here = Path(__file__).parent
    for p in (here/"background.png", here/"assets"/"background.png"):
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{b64}"
    return None

_bg = _bg_data_uri()

# ============================================================================
# CSS FIXO (sem formatação)
# ============================================================================
st.markdown("""
<style>
/* some resets */
header[data-testid="stHeader"]{ display:none !important; }
div[data-testid="stToolbar"]{ display:none !important; }
#MainMenu, footer{ visibility:hidden; }

/* evita menu multipágina padrão */
[data-testid="stSidebarNav"]{ display:none !important; }
div[data-testid="collapsedControl"]{ display:block !important; }

/* container topo mais próximo */
.block-container{ padding-top:.5rem !important; }

/* tipografia & campos */
* { color:#111 !important; }
a { color:#111 !important; text-decoration: underline; }
.stTextInput input, .stPassword input {
  background:#fff !important; color:#111 !important;
  border:1px solid #d0d7e2 !important; border-radius:10px !important;
}

/* cards */
.login-card{
  padding:22px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow:0 8px 24px rgba(0,0,0,.06); background:#ffffff !important;
}
.login-title{ font-size:18px; margin:0 0 14px 0; font-weight:800; }

/* TÍTULOS */
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

/* CTA */
.btn-primary, .btn-ghost{
  display:inline-block; padding:10px 16px; border-radius:10px; text-decoration:none!important;
  border:1px solid #111; background:#fff; color:#111!important;
}
.cta-row{ display:flex; gap:12px; margin-top:8px; }

/* Footer app */
.footer{
  margin-top:40px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#444!important;
}

/* camadas para o BG que será injetado abaixo */
.block-container, [data-testid="stSidebar"], header, footer { position:relative; z-index:1; }

/* ---------------- PÍLULA DE IDIOMA (flags + toggle) ---------------- */
.lang-pill {
  position: fixed;
  top: 14px;
  left: 18px;
  z-index: 1001;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border: 1px solid rgba(0,0,0,.08);
  border-radius: 999px;
  background: rgba(255,255,255,.85);
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 10px rgba(0,0,0,.06);
  font-weight: 600;
  line-height: 1;
}
.lang-pill [data-testid="stCheckbox"] label,
.lang-pill [data-testid="stToggle"] label { margin-bottom:0 !important; }
@media (max-width:640px){ .lang-pill{ padding:4px 8px; gap:8px; } }
</style>
""", unsafe_allow_html=True)

# BG (injetado num style separado para não conflitar com % / formatação)
if _bg:
    st.markdown(
        f"""
<style>
[data-testid="stAppViewContainer"]::before {{
  content:"";
  position:fixed; inset:0; z-index:0; pointer-events:none;
  background:#f5f5f5 url("{_bg}") no-repeat center top;
  background-size: clamp(900px, 85vw, 1600px) auto;
  opacity:.50; filter: contrast(103%) brightness(101%);
}}
</style>
""",
        unsafe_allow_html=True,
    )

# Render da pílula de idioma (UI)
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

st.markdown("""
<div class="lang-pill">
  <span>🇧🇷</span><span style="opacity:.75">PT</span>
  <span style="opacity:.35">|</span>
  <span style="opacity:.75">EN</span><span>🇬🇧</span>
</div>
""", unsafe_allow_html=True)

# toggle funcional (posicionado junto à pílula)
lang_holder = st.empty()
with lang_holder.container():
    st.markdown("<div style='position:fixed;top:14px;left:96px;z-index:1002;'>", unsafe_allow_html=True)
    en_on = st.toggle("", value=(st.session_state.lang == "en"), key="lang_toggle")
    st.markdown("</div>", unsafe_allow_html=True)
st.session_state.lang = "en" if en_on else "pt"

# ============================================================================
# I18N
# ============================================================================
TXT = {
    "pt": {
        "eyebrow":"OGMP 2.0 – L5",
        "title":"PLATAFORMA DE MONITORAMENTO DE METANO POR SATÉLITE",
        "subtitle":"Detecção, quantificação e relatórios automatizados de metano com dados multissatélite.",
        "bul1":"Detecção e priorização de eventos",
        "bul2":"Relatórios OGMP 2.0 e auditoria",
        "bul3":"Geoportal com mapas e séries históricas",
        "secure":"Acesso Seguro",
        "username":"Usuário",
        "password":"Senha",
        "signin":"Entrar",
        "forgot":"Esqueci minha senha",
        "badcreds":"Usuário ou senha inválidos.",
        "hint":"Faça login para continuar.",
        "confidential":"Acesso restrito. Conteúdo confidencial.",
        "logged_as":"Logado como",
        "support":"Suporte",
        "privacy":"Privacidade",
        "internal_use":"Uso interno",
        "change_required":"Você está usando senha provisória. Defina uma nova senha para continuar.",
        "old_pwd":"Senha atual",
        "new_pwd":"Nova senha",
        "new_pwd2":"Repita a nova senha",
        "save_new":"Salvar nova senha",
        "pwd_changed":"Senha alterada com sucesso ✅",
        "pwd_error":"Erro ao validar a troca de senha.",
        "reset_title":"Recuperar senha",
        "reset_info":"Geramos um código de redefinição e salvamos em users.json. Caso o envio de e-mail esteja configurado no servidor, você o receberá.",
        "gen_code":"Gerar código de redefinição",
        "code_ok":"Código gerado e salvo no GitHub. Contate o suporte se não receber o e-mail.",
        "gh_warn":"⚠️ Configure github_token e repo_users em st.secrets para carregar/salvar usuários.",
    },
    "en": {
        "eyebrow":"OGMP 2.0 – L5",
        "title":"SATELLITE METHANE MONITORING PLATFORM",
        "subtitle":"Detection, quantification, and automated reporting from multi-satellite data.",
        "bul1":"Event detection & prioritization",
        "bul2":"OGMP 2.0 reporting & audit",
        "bul3":"Geoportal with maps & time series",
        "secure":"Secure Access",
        "username":"Username",
        "password":"Password",
        "signin":"Sign in",
        "forgot":"Forgot my password",
        "badcreds":"Invalid username or password.",
        "hint":"Please sign in to continue.",
        "confidential":"Restricted access. Confidential content.",
        "logged_as":"Signed in as",
        "support":"Support",
        "privacy":"Privacy",
        "internal_use":"Internal use",
        "change_required":"You’re using a provisional password. Set a new one to continue.",
        "old_pwd":"Current password",
        "new_pwd":"New password",
        "new_pwd2":"Repeat new password",
        "save_new":"Save new password",
        "pwd_changed":"Password changed successfully ✅",
        "pwd_error":"Error validating password change.",
        "reset_title":"Password recovery",
        "reset_info":"A reset code was generated and saved in users.json. If e-mail delivery is configured, you’ll receive it.",
        "gen_code":"Generate reset code",
        "code_ok":"Reset code generated and saved to GitHub. Contact support if you don’t receive the e-mail.",
        "gh_warn":"⚠️ Configure github_token and repo_users in st.secrets to load/save users.",
    }
}
t = TXT[st.session_state.lang]

# ============================================================================
# GITHUB (users.json)
# ============================================================================
USERS_FILE = "users.json"

def gh_read_json(repo: str, path: str) -> Tuple[Dict[str, Any], Optional[str]]:
    if not repo or not GITHUB_TOKEN:
        return {}, None
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content), data.get("sha")
    return {}, None

def gh_write_json(repo: str, path: str, content: dict, message: str, sha: Optional[str]) -> bool:
    if not repo or not GITHUB_TOKEN:
        return False
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(json.dumps(content, indent=2).encode()).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=HEADERS, json=payload, timeout=25)
    return r.status_code in (200, 201)

def load_users():
    cfg, sha = gh_read_json(REPO_USERS, USERS_FILE)
    return cfg, sha

def save_users(cfg, msg, sha):
    return gh_write_json(REPO_USERS, USERS_FILE, cfg, msg, sha)

def hash_pwd(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_pwd(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

# ============================================================================
# UI (layout)
# ============================================================================
left, right = st.columns([1.15, 1], gap="large")

with left:
    # Logo se existir
    for cand in ("dapatlas.png","dapatlas.jpeg","logo.png","logo.jpeg","logomavipe.jpeg"):
        if Path(cand).exists():
            st.image(Image.open(cand), width=180)
            break

    st.markdown(f'<div class="hero-eyebrow">{t["eyebrow"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-title">{t["title"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-sub">{t["subtitle"]}</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <ul>
      <li>{t['bul1']}</li>
      <li>{t['bul2']}</li>
      <li>{t['bul3']}</li>
    </ul>
    """, unsafe_allow_html=True)

with right:
    st.markdown(f"<div class='login-card'><div class='login-title'>{t['secure']}</div>", unsafe_allow_html=True)

    if not (GITHUB_TOKEN and REPO_USERS):
        st.warning(t["gh_warn"])

    # ---- LOGIN FORM
    username = st.text_input(t["username"])
    password = st.text_input(t["password"], type="password")
    cols = st.columns([1,1.2,1.8])
    with cols[0]:
        submit = st.button(t["signin"])
    with cols[1]:
        forgot_clicked = st.button(t["forgot"])

    st.caption(t["confidential"])
    st.markdown("</div>", unsafe_allow_html=True)  # fecha card

# ---- LOGIN HANDLER
if submit:
    users_cfg, users_sha = load_users()
    user_rec = users_cfg.get("users", {}).get(username) if users_cfg else None
    if not user_rec or not check_pwd(password, user_rec.get("password", "")):
        st.error(t["badcreds"])
    else:
        st.session_state["authentication_status"] = True
        st.session_state["username"] = username
        st.session_state["name"] = user_rec.get("name", username)
        st.session_state["must_change"] = bool(user_rec.get("must_change", False))
        st.session_state["users_cfg"] = users_cfg
        st.session_state["users_sha"] = users_sha
        st.toast("✅ OK", icon="✅")
        st.experimental_rerun()

# ---- ESQUECI MINHA SENHA (gera reset_code)
if forgot_clicked:
    users_cfg, users_sha = load_users()
    st.info(f"**{t['reset_title']}** — {t['reset_info']}")
    u = st.text_input("Username / e-mail")
    if st.button(t["gen_code"], type="secondary"):
        if not users_cfg:
            st.error("users.json não disponível.")
        else:
            import secrets
            code = secrets.token_urlsafe(8)
            # procura por username ou e-mail
            key = None
            if "users" in users_cfg and u in users_cfg["users"]:
                key = u
            else:
                for k, rec in users_cfg["users"].items():
                    if str(rec.get("email","")).strip().lower() == u.strip().lower():
                        key = k
                        break
            if key:
                users_cfg["users"][key]["reset_code"] = code
                ok = save_users(users_cfg, f"Password reset code for {key}", users_sha)
                if ok:
                    st.success(t["code_ok"] + f" (code: **{code}**)")
                else:
                    st.error("Falha ao salvar no GitHub.")
            else:
                st.error("Usuário não encontrado.")

# ============================================================================
# ESTADO PÓS-LOGIN
# ============================================================================
def _first_existing(*paths: str) -> Optional[str]:
    for p in paths:
        if Path(p).exists():
            return p
    return None

GEO_PAGE = _first_existing("2_Geoportal.py", "pages/2_Geoportal.py")
AGENDA_PAGE = _first_existing("4_Agendamento_de_Imagens.py", "pages/4_Agendamento_de_Imagens.py")
RELATORIO_PAGE = _first_existing("3_Relatorio_OGMP_2_0.py", "pages/3_Relatorio_OGMP_2_0.py")
ESTATS_PAGE = _first_existing("1_Estatisticas_Gerais.py", "pages/1_Estatisticas_Gerais.py")

auth_ok = st.session_state.get("authentication_status", False)
if auth_ok:
    # Troca obrigatória de senha?
    if st.session_state.get("must_change", False):
        st.warning(t["change_required"])
        with st.form("change_pwd"):
            old = st.text_input(t["old_pwd"], type="password")
            new1 = st.text_input(t["new_pwd"], type="password")
            new2 = st.text_input(t["new_pwd2"], type="password")
            ok = st.form_submit_button(t["save_new"])
        if ok:
            cfg = st.session_state.get("users_cfg", {})
            sha = st.session_state.get("users_sha")
            uname = st.session_state.get("username")
            rec = cfg.get("users", {}).get(uname, {})
            if rec and check_pwd(old, rec.get("password","")) and new1 == new2 and len(new1) >= 8:
                rec["password"] = hash_pwd(new1)
                rec["must_change"] = False
                saved = save_users(cfg, f"Password change for {uname}", sha)
                if saved:
                    st.success(t["pwd_changed"])
                    st.session_state["must_change"] = False
                    st.experimental_rerun()
                else:
                    st.error("Falha ao salvar nova senha no GitHub.")
            else:
                st.error(t["pwd_error"])
    else:
        # Sidebar com módulos
        st.sidebar.success(f'{t["logged_as"]}: {st.session_state.get("name")}')
        if GEO_PAGE:       st.sidebar.page_link(GEO_PAGE, label="🗺️ Geoportal")
        if AGENDA_PAGE:    st.sidebar.page_link(AGENDA_PAGE, label="🗓️ Agendamento de imagens")
        if RELATORIO_PAGE: st.sidebar.page_link(RELATORIO_PAGE, label="📄 Relatório OGMP 2.0")
        if ESTATS_PAGE:    st.sidebar.page_link(ESTATS_PAGE, label="📊 Estatísticas")
        if st.sidebar.button("Sair"):
            st.session_state.clear()
            st.experimental_rerun()

        # Redireciona automaticamente pro Geoportal (uma vez)
        if not st.session_state.get("redirected_to_geoportal"):
            st.session_state["redirected_to_geoportal"] = True
            target = GEO_PAGE or AGENDA_PAGE or RELATORIO_PAGE or ESTATS_PAGE
            if target:
                try:
                    st.switch_page(target)
                except Exception:
                    st.info("Login OK! Use os atalhos na barra lateral para abrir os módulos.")

# ============================================================================
# FOOTER
# ============================================================================
APP_VERSION = os.getenv("APP_VERSION","v1.0.0")
ENV_LABEL = "Produção"
st.markdown(f"""
<div class="footer">
  <div>DAP ATLAS · {APP_VERSION} · Ambiente: {ENV_LABEL}</div>
  <div>{t["internal_use"]} · <a href="mailto:support@dapsistemas.com">{t["support"]}</a> · 
       <a href="https://example.com/privacidade" target="_blank">{t["privacy"]}</a></div>
</div>
""", unsafe_allow_html=True)
