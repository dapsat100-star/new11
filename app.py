# -*- coding: utf-8 -*-
# app.py — Login OGMP (GitHub users.json) + Esqueci Minha Senha + Toggle PT/EN

import os
import io
import json
import base64
import secrets
import requests
import bcrypt
from pathlib import Path
from datetime import datetime, timezone, timedelta

import streamlit as st
from PIL import Image

# =========================
# CONFIG / SECRETS
# =========================
st.set_page_config(
    page_title="Plataforma OGMP 2.0",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Secrets esperados
GITHUB_TOKEN  = st.secrets.get("github_token")
REPO_USERS    = st.secrets.get("repo_users")       # ex: "dapsat100-star/new11"
GITHUB_BRANCH = st.secrets.get("github_branch", "main")

HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

USERS_FILE = "users.json"

# =========================
# I18N (toggle canto esquerdo)
# =========================
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

st.markdown("""
<style>
/* esconde header nativo e toolbar */
header[data-testid="stHeader"]{display:none!important;}
div[data-testid="stToolbar"]{display:none!important;}
#MainMenu, footer{visibility:hidden;}

/* toggle no topo esquerdo */
.lang-toggle{
  position: fixed; top: 10px; left: 14px; z-index: 1000;
  background: #fff; border: 1px solid #e7e7e7; border-radius: 12px;
  padding: 6px 10px; box-shadow: 0 4px 14px rgba(0,0,0,.06);
}
.login-card{
  padding:24px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow:0 8px 24px rgba(0,0,0,.06); background:#fff;
}
.hero-title{font-size:46px; font-weight:900; letter-spacing:-.02em; margin:0 0 10px 0;}
.hero-sub{font-size:16px; color:#222; max-width:60ch; margin:0 0 14px 0;}
.cta li{margin:6px 0;}
</style>
""", unsafe_allow_html=True)

with st.container():
    col = st.columns([1,9])[0]
    with col:
        st.markdown('<div class="lang-toggle">', unsafe_allow_html=True)
        lang_toggle = st.toggle("English", value=(st.session_state.lang=="en"), key="lang_toggle_main")
        st.markdown('</div>', unsafe_allow_html=True)
        st.session_state.lang = "en" if lang_toggle else "pt"

TXT = {
    "pt": {
        "eyebrow": "OGMP 2.0 – L5",
        "title": "Plataforma de Monitoramento de Metano por Satélite",
        "subtitle": "Detecção, quantificação e relatórios automatizados com dados multissatélite.",
        "bul1": "Detecção e priorização de eventos",
        "bul2": "Relatórios OGMP 2.0 e auditoria",
        "bul3": "Geoportal com mapas e séries históricas",
        "secure": "Acesso Seguro",
        "user": "Usuário",
        "pass": "Senha",
        "login": "Entrar",
        "badcred": "Usuário ou senha inválidos.",
        "hint": "Faça login para continuar.",
        "forgot": "Esqueci minha senha",
        "gen_code": "1) Gerar código",
        "apply_code": "2) Definir nova senha",
        "gen_btn": "Gerar código de reset",
        "apply_btn": "Salvar nova senha",
        "user_not_found": "Usuário não encontrado.",
        "fill_all": "Preencha todos os campos.",
        "mismatch": "As senhas não coincidem.",
        "len8": "A nova senha precisa ter pelo menos 8 caracteres.",
        "code_gen_ok": "Código gerado! Use na próxima aba em até 15 min.",
        "code_shown": "Código",
        "code_bad": "Código inválido ou expirado.",
        "pwd_changed": "Senha alterada com sucesso! Faça login com a nova senha.",
        "confidential": "Acesso restrito. Conteúdo confidencial.",
        "signed_as": "Logado como",
        "go_geo": "Abrir Geoportal",
        "modules": "Módulos",
        "support": "Suporte",
        "privacy": "Privacidade",
        "no_secrets": "Atenção: configure github_token e repo_users em secrets."
    },
    "en": {
        "eyebrow": "OGMP 2.0 – L5",
        "title": "Satellite Methane Monitoring Platform",
        "subtitle": "Detection, quantification and automated reporting from multi-satellite data.",
        "bul1": "Event detection & prioritization",
        "bul2": "OGMP 2.0 reporting & audit",
        "bul3": "Geoportal with maps & time series",
        "secure": "Secure Access",
        "user": "Username",
        "pass": "Password",
        "login": "Sign in",
        "badcred": "Invalid username or password.",
        "hint": "Sign in to continue.",
        "forgot": "Forgot my password",
        "gen_code": "1) Generate code",
        "apply_code": "2) Set new password",
        "gen_btn": "Generate reset code",
        "apply_btn": "Save new password",
        "user_not_found": "User not found.",
        "fill_all": "Fill in all fields.",
        "mismatch": "Passwords don’t match.",
        "len8": "New password must be at least 8 characters.",
        "code_gen_ok": "Code generated! Use it on the next tab within 15 minutes.",
        "code_shown": "Code",
        "code_bad": "Invalid or expired code.",
        "pwd_changed": "Password changed! Please sign in with the new password.",
        "confidential": "Restricted access. Confidential content.",
        "signed_as": "Signed in as",
        "go_geo": "Open Geoportal",
        "modules": "Modules",
        "support": "Support",
        "privacy": "Privacy",
        "no_secrets": "Warning: configure github_token and repo_users in secrets."
    },
}
t = TXT[st.session_state.lang]

# =========================
# GitHub util
# =========================
def github_load_json(repo: str, path: str):
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
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

def github_save_json(repo: str, path: str, content: dict, message: str, sha: str | None):
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

# wrappers
def load_users():
    return github_load_json(REPO_USERS, USERS_FILE)

def save_users(data, message, sha):
    return github_save_json(REPO_USERS, USERS_FILE, data, message, sha)

# =========================
# Password helpers
# =========================
def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _gen_reset_code(n: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(n))

def _is_reset_code_valid(rec: dict, code: str) -> bool:
    r = (rec or {}).get("reset") or {}
    if not r:
        return False
    if str(r.get("code")) != str(code):
        return False
    try:
        exp = datetime.fromisoformat(r["expires"].replace("Z", "+00:00"))
    except Exception:
        return False
    return datetime.now(timezone.utc) <= exp

# =========================
# HERO + LOGIN
# =========================
left, right = st.columns([1.35, 1], gap="large")

with left:
    # Logo (opcional)
    for cand in ("dapatlas.png","logo.png","logomavipe.jpeg"):
        if Path(cand).exists():
            st.image(Image.open(cand), width=160)
            break
    st.caption(t["eyebrow"])
    st.markdown(f"<div class='hero-title'>{t['title']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-sub'>{t['subtitle']}</div>", unsafe_allow_html=True)
    st.markdown("<ul class='cta'>"
                f"<li>• {t['bul1']}</li>"
                f"<li>• {t['bul2']}</li>"
                f"<li>• {t['bul3']}</li>"
                "</ul>", unsafe_allow_html=True)

with right:
    st.markdown(f"<div class='login-card'><h3>{t['secure']}</h3>", unsafe_allow_html=True)

    if not (GITHUB_TOKEN and REPO_USERS):
        st.warning(t["no_secrets"])

    username = st.text_input(t["user"])
    password = st.text_input(t["pass"], type="password")
    login_btn = st.button(t["login"])

    # ========= Esqueci minha senha =========
    with st.expander(t["forgot"], expanded=False):
        st.caption("Sem e-mail: o código aparece aqui e vale por 15 minutos." if st.session_state.lang=="pt"
                   else "No email: code is shown here and is valid for 15 minutes.")
        tabs = st.tabs([t["gen_code"], t["apply_code"]])

        with tabs[0]:
            u1 = st.text_input(t["user"], key="reset_user_req").strip()
            if st.button(t["gen_btn"]):
                if not u1:
                    st.warning(t["fill_all"])
                else:
                    users_cfg, users_sha = load_users()
                    user_rec = users_cfg.get("users", {}).get(u1)
                    if not user_rec:
                        st.error(t["user_not_found"])
                    else:
                        code = _gen_reset_code(6)
                        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat().replace("+00:00","Z")
                        users_cfg["users"][u1]["reset"] = {"code": code, "expires": expires, "created_at": _now_utc_iso()}
                        ok = save_users(users_cfg, f"[reset] code for {u1}", users_sha)
                        if ok:
                            st.success(t["code_gen_ok"])
                            st.code(code, language="text")
                        else:
                            st.error("GitHub save error.")

        with tabs[1]:
            u2 = st.text_input(t["user"], key="reset_user_apply").strip()
            c2 = st.text_input(t["code_shown"], key="reset_code_apply").strip()
            n1 = st.text_input("Nova senha" if st.session_state.lang=="pt" else "New password", type="password", key="reset_new1")
            n2 = st.text_input("Repita a nova senha" if st.session_state.lang=="pt" else "Repeat new password", type="password", key="reset_new2")
            if st.button(t["apply_btn"]):
                if not (u2 and c2 and n1 and n2):
                    st.warning(t["fill_all"])
                elif n1 != n2:
                    st.warning(t["mismatch"])
                elif len(n1) < 8:
                    st.warning(t["len8"])
                else:
                    users_cfg, users_sha = load_users()
                    user_rec = users_cfg.get("users", {}).get(u2)
                    if not user_rec:
                        st.error(t["user_not_found"])
                    elif not _is_reset_code_valid(user_rec, c2):
                        st.error(t["code_bad"])
                    else:
                        users_cfg["users"][u2]["password"] = hash_password(n1)
                        users_cfg["users"][u2]["must_change"] = False
                        users_cfg["users"][u2].pop("reset", None)
                        ok = save_users(users_cfg, f"[reset] apply for {u2}", users_sha)
                        if ok:
                            st.success(t["pwd_changed"])
                        else:
                            st.error("GitHub save error.")

    st.markdown(f"<div style='color:#666;margin-top:8px'>{t['confidential']}</div></div>", unsafe_allow_html=True)

# =========================
# Autenticação
# =========================
if login_btn:
    users_cfg, users_sha = load_users()
    user_rec = users_cfg.get("users", {}).get(username)
    if not user_rec or not check_password(password, user_rec["password"]):
        st.error(t["badcred"])
    else:
        st.session_state["authentication_status"] = True
        st.session_state["name"] = user_rec.get("name") or username
        st.session_state["username"] = username
        st.session_state["must_change"] = user_rec.get("must_change", False)
        st.session_state["users_sha"] = users_sha
        st.session_state["users_cfg"] = users_cfg
        st.success("Login OK!")

        # Redireciona ao Geoportal se existir
        target = None
        for cand in ("pages/2_Geoportal.py", "2_Geoportal.py"):
            if Path(cand).exists():
                target = cand
                break
        if target:
            try:
                st.switch_page(target)
            except Exception:
                pass

# =========================
# Área autenticada (sidebar com módulos)
# =========================
auth_ok = st.session_state.get("authentication_status", False)
if auth_ok:
    st.sidebar.success(f"{t['signed_as']}: {st.session_state.get('name')}")
    # links se existirem
    pages = [
        ("pages/2_Geoportal.py", "Geoportal", "🗺️"),
        ("pages/4_Agendamento_de_Imagens.py", "Agendamento de Imagens", "🗓️"),
        ("pages/3_Relatorio_OGMP_2_0.py", "Relatório OGMP 2.0", "📄"),
        ("pages/1_Estatisticas_Gerais.py", "Estatísticas", "📊"),
    ]
    st.sidebar.markdown(f"### {t['modules']}")
    for p, label, icon in pages:
        if Path(p).exists():
            st.sidebar.page_link(p, label=label, icon=icon)

# =========================
# Footer
# =========================
st.markdown(
    f"""
<div style="margin-top:36px; padding:16px 0; border-top:1px solid #eee; font-size:12px; color:#555;">
  DAP ATLAS · {t['confidential']} · 
  <a href="mailto:support@dapsistemas.com">{t['support']}</a> · 
  <a target="_blank" href="https://example.com/privacy">{t['privacy']}</a>
</div>
""",
    unsafe_allow_html=True,
)
