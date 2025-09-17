# -*- coding: utf-8 -*-
import os
from pathlib import Path
import yaml
from yaml.loader import SafeLoader
import streamlit as st
from dotenv import load_dotenv
from PIL import Image
import streamlit_authenticator as stauth
import base64

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
st.set_page_config(
    page_title="Plataforma de Metano OGMP 2.0 - L5",
    page_icon="favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)
load_dotenv()

# ------------------------------------------------------------
# Oculta header/toolbar/menu e sidebar no login
# ------------------------------------------------------------
st.markdown("""
<style>
/* header/toolbar/menus padrão do Streamlit */
header[data-testid="stHeader"]{display:none!important;}
div[data-testid="stToolbar"]{display:none!important;}
#MainMenu{visibility:hidden;}
footer{visibility:hidden;}

/* sidebar e o "handle" para abrir (no login) */
[data-testid="stSidebar"]{display:none!important;}
div[data-testid="collapsedControl"]{display:none!important;}

/* reduz espaço no topo e puxa conteúdo pra cima */
[data-testid="stAppViewContainer"]{ padding-top: 0 !important; }
.block-container{ padding-top: .5rem !important; }
.lang-row{ position:absolute; top:8px; left:16px; }

/* tipografia e inputs padrão */
* { color:#111111 !important; }
a { color:#111111 !important; text-decoration: underline; }
input, textarea, select, .stTextInput input, .stPassword input {
  background:#ffffff !important; color:#111111 !important;
  border:1px solid #d0d7e2 !important; border-radius:10px !important;
}
input::placeholder, textarea::placeholder { color:#444444 !important; opacity:1 !important; }

/* cartão do login */
.login-card{
  padding:24px; border:1px solid #e7e7e7; border-radius:16px;
  box-shadow: 0 8px 24px rgba(0,0,0,.06); background:#ffffff !important;
}
.login-title{ font-size:18px; margin:0 0 14px 0; font-weight:700; }

/* ===== HERO LAYOUT (como no print) ===== */
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
@media (min-width:1200px){ .hero-title{ font-size:48px; } }
.hero-sub{ font-size:16px; color:#222; max-width:56ch; margin:0 0 10px 0; }
.hero-bullets{ margin:8px 0 18px 18px; }
.hero-bullets li{ margin:6px 0; }

/* botões estilo do print */
.btn-primary, .btn-ghost{
  display:inline-block; padding:10px 16px; border-radius:10px; text-decoration:none!important;
  border:1px solid #111; background:#fff; color:#111!important;
}
.cta-row{ display:flex; gap:12px; margin-top:8px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# Fundo com imagem local (background.png → base64)
# ------------------------------------------------------------
def _bg_data_uri():
    here = Path(__file__).parent
    candidates = [here/"background.png", here/"assets"/"background.png"]
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
      background-size: clamp(900px, 85vw, 1600px) auto;  /* tamanho controlado */
      opacity: .50;
      filter: contrast(103%) brightness(101%);
    }}
    .block-container, [data-testid="stSidebar"], header, footer {{
      position: relative; z-index: 1;
    }}
    @media (max-width: 1200px){{
      [data-testid="stAppViewContainer"]::before {{
        background-size: clamp(780px, 90vw, 1100px) auto;
        opacity:.45;
      }}
    }}
    @media (max-width: 768px){{
      [data-testid="stAppViewContainer"]::before {{
        background-size: 700px auto;
        background-position: center 40px;
        opacity:.40;
      }}
    }}
    </style>
    """, unsafe_allow_html=True)
else:
    st.warning("⚠️ 'background.png' não foi encontrado (raiz ou assets/).")

# ------------------------------------------------------------
# i18n
# ------------------------------------------------------------
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

st.markdown('<div class="lang-row">', unsafe_allow_html=True)
lang_toggle = st.toggle("English", value=(st.session_state.lang=="en"), key="lang_toggle")
st.markdown('</div>', unsafe_allow_html=True)
st.session_state.lang = "en" if lang_toggle else "pt"

TXT = {
  "pt": {"eyebrow":"Plataforma OGMP 2.0 – L5","title":"PLATAFORMA DE MONITORAMENTO DE METANO POR SATÉLITE",
         "subtitle":"Detecção, quantificação e insights acionáveis a partir de dados multissatélite. Confiabilidade de nível industrial.",
         "bul1":"Detecção e priorização de eventos","bul2":"Relatórios OGMP 2.0 e auditoria","bul3":"Geoportal com mapas, KPIs e séries históricas",
         "cta_login":"Login","cta_about":"Saiba mais","secure_access":"Acesso Seguro","login_hint":"Por favor, faça login para continuar.",
         "bad_credentials":"Usuário ou senha inválidos.","confidential":"Acesso restrito. Conteúdo confidencial.",
         "logged_as":"Logado como","support":"Suporte","privacy":"Privacidade","internal_use":"Uso interno"},
  "en": {"eyebrow":"OGMP 2.0 Platform – L5","title":"SATELLITE METHANE MONITORING PLATFORM",
         "subtitle":"Detection, quantification, and actionable insights from multi-satellite data. Industrial-grade reliability.",
         "bul1":"Event detection & prioritization","bul2":"OGMP 2.0 reporting & audit","bul3":"Geoportal with maps, KPIs, time series",
         "cta_login":"Login","cta_about":"Learn more","secure_access":"Secure Access","login_hint":"Please sign in to continue.",
         "bad_credentials":"Invalid username or password.","confidential":"Restricted access. Confidential content.",
         "logged_as":"Signed in as","support":"Support","privacy":"Privacy","internal_use":"Internal use"}
}
t = TXT[st.session_state.lang]

# ------------------------------------------------------------
# Mostrar sidebar após login
# ------------------------------------------------------------
def show_sidebar():
    st.markdown("""
    <style>
      [data-testid='stSidebar']{display:flex!important;}
      div[data-testid="collapsedControl"]{display:block!important;}
    </style>
    """, unsafe_allow_html=True)

# ------------------------------------------------------------
# Autenticação
# ------------------------------------------------------------
def build_authenticator() -> stauth.Authenticate:
    with open("auth_config.yaml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=SafeLoader)
    return stauth.Authenticate(
        config["credentials"], config["cookie"]["name"],
        config["cookie"]["key"], config["cookie"]["expiry_days"]
    )
authenticator = build_authenticator()

# ------------------------------------------------------------
# Layout (hero + login)
# ------------------------------------------------------------
left, right = st.columns([1.15, 1], gap="large")

with left:
    st.markdown("<div class='hero-wrap'>", unsafe_allow_html=True)

    # logo em “cartão”
    for cand in ("dapatlas.png","dapatlas.jpeg","logo.png","logo.jpeg"):
        if Path(cand).exists():
            st.markdown("<div class='logo-card'>", unsafe_allow_html=True)
            st.image(Image.open(cand), width=180)  # sem use_column_width
            st.markdown("</div>", unsafe_allow_html=True)
            break

    # eyebrow + textos
    st.markdown(f'<div class="hero-eyebrow">{t["eyebrow"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-title">{t["title"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-sub">{t["subtitle"]}</div>', unsafe_allow_html=True)

    # bullets
    st.markdown(f"""
    <ul class='hero-bullets'>
      <li>{t['bul1']}</li>
      <li>{t['bul2']}</li>
      <li>{t['bul3']}</li>
    </ul>
    """, unsafe_allow_html=True)

    # botões
    st.markdown(
        f"<div class='cta-row'><a class='btn-primary' href='#login'>{t['cta_login']}</a>"
        f"<a class='btn-ghost' href='mailto:support@dapsistemas.com'>{t['cta_about']}</a></div>",
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown(
        f"<div id='login' class='login-card'><div class='login-title'>{t['secure_access']}</div>",
        unsafe_allow_html=True
    )
    fields = {"Form name": "", "Username": "Usuário", "Password": "Senha", "Login": "Entrar"}
    try:
        name, auth_status, username = authenticator.login("main", fields=fields)
    except TypeError:
        name, auth_status, username = authenticator.login("main")
    st.markdown(f"<div class='login-note'>{t['confidential']}</div></div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# UX do login (olho senha + lembrar usuário)
# ------------------------------------------------------------
def apply_ux_enhancements():
    st.markdown("""
    <style>
      .pw-eye {position:absolute; right:10px; top:50%; transform: translateY(-50%);
        border:0; background:transparent; cursor:pointer; font-size:16px; padding:2px; line-height:1;}
      .pw-wrap { position:relative; }
      .caps-hint { margin-top:6px; font-size:12px; color:#d00; }
      .remember-row { display:flex; align-items:center; gap:8px; font-size:13px;
        margin:6px 0 10px 2px; color:#111;}
      .remember-row input[type="checkbox"]{ transform: scale(1.1); }
      @media (max-width: 780px){ .footer{ position: static; } }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <script>
    (function(){
      const root = document.getElementById('login') || document.body;
      function onceReady(fn){
        let tries = 0;
        const iv = setInterval(()=>{
          tries++;
          const u = root.querySelector('input[type="text"]');
          const p = root.querySelector('input[type="password"]');
          const btn = root.querySelector('button');
          if ((u || p) && btn){ clearInterval(iv); fn({u,p,btn}); }
          if (tries > 25) clearInterval(iv);
        }, 180);
      }
      onceReady(({u,p,btn})=>{
        if (u && !u.placeholder) u.placeholder = "Usuário";
        if (p && !p.placeholder) p.placeholder = "Senha";
        if (u){
          const saved = localStorage.getItem('dap_username') || "";
          if (saved && !u.value) u.value = saved;
          const row = document.createElement('label');
          row.className = 'remember-row';
          row.innerHTML = "<input type='checkbox' id='rememberUser'> <span>Lembrar usuário</span>";
          (u.parentElement?.parentElement || u.parentElement).insertAdjacentElement('afterend', row);
          const cb = row.querySelector('#rememberUser');
          cb.checked = !!saved;
          const store = () => { cb.checked ? localStorage.setItem('dap_username', u.value) : localStorage.removeItem('dap_username'); };
          u.addEventListener('input', store); cb.addEventListener('change', store);
        }
        if (p){
          if (!p.parentElement.classList.contains('pw-wrap')) p.parentElement.classList.add('pw-wrap');
          const eye = document.createElement('button');
          eye.type = 'button'; eye.className = 'pw-eye';
          eye.setAttribute('aria-label','Mostrar/ocultar senha');
          eye.textContent = '👁';
          p.parentElement.appendChild(eye);
          eye.addEventListener('click', ()=>{ p.type = (p.type === 'password' ? 'text' : 'password'); });
          const hint = document.createElement('div');
          hint.className = 'caps-hint';
          hint.textContent = 'Caps Lock ativo';
          hint.style.display = 'none';
          p.parentElement.appendChild(hint);
          p.addEventListener('keyup', (e)=>{ hint.style.display = (e.getModifierState && e.getModifierState('CapsLock')) ? 'block' : 'none'; });
        }
        (u || p)?.focus();
        [u,p].forEach(el => el && el.addEventListener('keydown', (e)=>{ if (e.key === 'Enter'){ btn?.click(); }}));
        if (btn){
          btn.addEventListener('click', ()=>{
            const old = btn.textContent;
            btn.disabled = true; btn.textContent = 'Entrando…';
            setTimeout(()=>{ btn.disabled = false; btn.textContent = old; }, 4000);
          });
        }
      });
    })();
    </script>
    """, unsafe_allow_html=True)

apply_ux_enhancements()

# ------------------------------------------------------------
# Estado do login
# ------------------------------------------------------------
if 'auth_status' in locals():
    if 'last_auth_status' not in st.session_state:
        st.session_state.last_auth_status = None
    if auth_status != st.session_state.last_auth_status:
        if auth_status is True:
            st.toast("Login realizado com sucesso. Bem-vindo!", icon="✅")
        elif auth_status is False:
            st.toast("Usuário ou senha inválidos.", icon="⚠️")
        st.session_state.last_auth_status = auth_status

    if auth_status is False:
        st.error(t["bad_credentials"])
    elif auth_status is None:
        st.info(t["login_hint"])

    if auth_status:
        show_sidebar()
        st.sidebar.success(f'{t["logged_as"]}: {name}')
        try:
            authenticator.logout(location="sidebar")
        except Exception:
            authenticator.logout("Sair", "sidebar")

# ------------------------------------------------------------
# Footer
# ------------------------------------------------------------
APP_VERSION = os.getenv("APP_VERSION","v1.0.0")
ENV_LABEL = "Produção"
st.markdown(f"""
<div class="footer">
  <div>DAP ATLAS · {APP_VERSION} · Ambiente: {ENV_LABEL}</div>
  <div>{t["internal_use"]} · <a href="mailto:support@dapsistemas.com">{t["support"]}</a> · 
       <a href="https://example.com/privacidade" target="_blank">{t["privacy"]}</a></div>
</div>
""", unsafe_allow_html=True)
