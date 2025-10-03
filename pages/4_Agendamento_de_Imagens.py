# -*- coding: utf-8 -*-
# pages/4_Agendamento_de_Imagens.py
# Cronograma de Passes de Satélites — UI SaaS, sidebar fixa, status badge,
# "Última atualização" com prioridade local e STATUS com cores (via ícones).

from __future__ import annotations

import io
import json
import time
import base64
import os
import datetime as dt
from pathlib import Path
from typing import Optional, List, Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ==== Guard de sessão ====
_is_auth = bool(st.session_state.get("user")) or bool(st.session_state.get("authentication_status"))
if not _is_auth:
    st.warning("Sessão expirada ou não autenticada.")
    st.page_link("app.py", label="🔐 Voltar à página de login")
    st.stop()

# ============================================================================
# CONFIG PÁGINA
# ============================================================================
st.set_page_config(
    page_title="🛰️ Cronograma de Passes de Satélites",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------- CSS ----------------
st.markdown(
    """
<style>
div[data-testid="collapsedControl"] { display: none !important; }

/* Sidebar fixa, 400px */
section[data-testid="stSidebar"], aside[data-testid="stSidebar"] {
  visibility: visible !important;
  transform: translateX(0) !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  width: 400px !important;
  min-width: 400px !important;
  background: #ffffff !important;
  border-right: 1px solid #eef0f3 !important;
  position: sticky !important;
  top: 0 !important;
  height: 100vh !important;
  overflow: auto !important;
  z-index: 100;
}

/* Oculta navegação automática */
div[data-testid="stSidebarNav"] { display: none !important; }
section[data-testid="stSidebar"] nav,
section[data-testid="stSidebar"] [role="navigation"] { display: none !important; }

/* Não truncar links do page_link */
section[data-testid="stSidebar"] a[role="link"],
section[data-testid="stSidebar"] [data-testid="stPageLink"] {
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
  display: block !important;
  line-height: 1.25 !important;
  word-break: break-word !important;
}

/* App bar */
.appbar {position: sticky; top: 0; z-index: 50; background:#ffffffcc; backdrop-filter: blur(8px);
  border-bottom:1px solid #eef0f3; margin-bottom:8px;}
.appbar-inner {display:flex; align-items:center; justify-content:space-between; padding:10px 0;}
.appbar h1 {font-size:1.6rem; margin:0;}
.appbar .meta {color:#6b7280; font-size:.9rem;}

/* Badge de status */
.status-badge {display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px; font-weight:600; font-size:.9rem;}
.status-ok {background:#e8faf0; color:#106c3a; border:1px solid #bff0cf;}
.status-err {background:#ffefef; color:#8a1414; border:1px solid #ffd0d0;}

/* Cards */
.card {background:#fff; border:1px solid #eef0f3; border-radius:16px;
  box-shadow:0 1px 2px rgba(16,24,40,.04); padding:16px; margin:12px 0;}
.card h3 {margin:0 0 8px 0; font-size:1.1rem}

/* Tabela: cabeçalho sticky */
[data-testid="stTable"] thead tr {position: sticky; top: 48px; background:#fff; z-index:5; box-shadow:0 1px 0 #eef0f3;}

header[data-testid="stHeader"]{ display:none !important; }

/* Inputs/chips sidebar */
section[data-testid="stSidebar"] {
  --sb-border: #d1d5db; --sb-border-strong: #9ca3af; --sb-bg: #fafafa; --sb-bg-focus: #ffffff; --sb-focus-ring: rgba(31,111,235,.18);
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
  border: 1.5px solid var(--sb-border) !important; background: var(--sb-bg) !important; border-radius: 10px !important;
  transition: border-color .15s ease, box-shadow .15s ease, background .15s ease;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover { border-color: var(--sb-border-strong) !important; }
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within {
  border-color: #1f6feb !important; background: var(--sb-bg-focus) !important; box-shadow: 0 0 0 3px var(--sb-focus-ring) !important;
}
section[data-testid="stSidebar"] div[data-baseweb="tag"] {
  background: #ffffff !important; color: #111827 !important; border: 1.2px solid var(--sb-border) !important;
  box-shadow: 0 1px 0 rgba(0,0,0,.04) !important; border-radius: 10px !important;
}
section[data-testid="stSidebar"] div[data-baseweb="tag"] svg { fill: #6b7280 !important; }
section[data-testid="stSidebar"] div[data-baseweb="tag"]:hover svg { fill: #374151 !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================================
# RERUN
# ============================================================================
def _rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ============================================================================
# LOGO (opcional)
# ============================================================================
def _logo_b64_from(path: str) -> Optional[str]:
    p = Path(path)
    if not p.exists(): return None
    try: return base64.b64encode(p.read_bytes()).decode("utf-8")
    except Exception: return None

_LOGO_B64 = _logo_b64_from("logomavipe.jpeg")
if _LOGO_B64:
    st.markdown(
        f"""
<div style="position:fixed;top:12px;right:20px;z-index:9999;pointer-events:none">
  <img src="data:image/jpeg;base64,{_LOGO_B64}" style="height:100px;width:auto;opacity:.98"/>
</div>
""",
        unsafe_allow_html=True,
    )

# ============================================================================
# GITHUB utils + status
# ============================================================================
def _conf_get(*keys, default: str = "") -> str:
    for k in keys:
        v = os.getenv(k) or (st.secrets.get(k) if hasattr(st, "secrets") else "")
        if v: return str(v)
    return default

def _gh_token() -> str:   return _conf_get("GITHUB_TOKEN", "github_token")
def _gh_repo()  -> str:   return _conf_get("REPO_CRONOGRAMA", "github_repo")
def _gh_branch()-> str:   return _conf_get("GITHUB_BRANCH", "github_branch", default="main")
def _gh_root()  -> str:   return _conf_get("GH_DATA_ROOT", "gh_data_root", "data_root", default="data/validado")

def _gh_headers() -> Dict[str,str]:
    h={"Accept":"application/vnd.github+json"}; tok=_gh_token()
    if tok: h["Authorization"]=f"Bearer {tok}"
    return h

def _ping_github(ttl: int = 120) -> bool:
    """Checagem leve de conectividade com cache em sessão."""
    key = "_gh_ping_cache"
    now = time.time()
    cache = st.session_state.get(key, {})
    entry = cache.get("ping")
    if entry and (now - entry["ts"] < ttl):
        return bool(entry["ok"])
    try:
        url = f"https://api.github.com/repos/{_gh_repo()}"
        r = requests.get(url, headers=_gh_headers(), timeout=5)
        ok = (200 <= r.status_code < 300)
    except Exception:
        ok = False
    cache["ping"] = {"ts": now, "ok": ok}
    st.session_state[key] = cache
    return ok

def _list_contents(path: str):
    url = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}?ref={_gh_branch()}"
    r = requests.get(url, headers=_gh_headers(), timeout=20)
    if r.status_code == 403 and "rate limit" in r.text.lower():
        raise RuntimeError("GitHub rate limit exceeded")
    r.raise_for_status()
    return r.json()

def _list_all_xlsx(path: str) -> List[str]:
    files: List[str] = []
    for it in _list_contents(path):
        if it["type"] == "file" and it["name"].lower().endswith(".xlsx"):
            files.append(it["path"])
        elif it["type"] == "dir":
            files.extend(_list_all_xlsx(it["path"]))
    return files

def gh_get_file_sha(path: str) -> Optional[str]:
    url = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}?ref={_gh_branch()}"
    r = requests.get(url, headers=_gh_headers(), timeout=20)
    return r.json().get("sha") if r.status_code == 200 else None

def gh_put_file(path: str, content_bytes: bytes, message: str, sha: Optional[str] = None):
    url = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}"
    payload = {"message": message, "content": base64.b64encode(content_bytes).decode("utf-8"),
               "branch": _gh_branch()}
    if sha: payload["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Falha ao salvar no GitHub ({r.status_code})")
    return r.json()

def gh_save_snapshot(xls_bytes: bytes, author: Optional[str] = None) -> dict:
    root = _gh_root().rstrip("/")
    now  = dt.datetime.now(dt.timezone.utc)
    yyyy = now.strftime("%Y"); mm = now.strftime("%m"); stamp = now.strftime("%Y%m%d-%H%M%S")
    excel_rel_path = f"{root}/{yyyy}/{mm}/validado-{stamp}.xlsx"
    gh_put_file(excel_rel_path, xls_bytes, f"[streamlit] snapshot {stamp} (autor={author or 'anon'})", None)
    latest = {"saved_at_utc": now.isoformat().replace("+00:00","Z")}
    latest_path = f"{root}/latest.json"
    sha_old = gh_get_file_sha(latest_path)
    gh_put_file(latest_path, json.dumps(latest, ensure_ascii=False, indent=2).encode("utf-8"),
                "[streamlit] update latest timestamp", sha_old)
    return latest

def load_latest_meta() -> Optional[dict]:
    try:
        root = _gh_root().rstrip("/")
        url = f"https://raw.githubusercontent.com/{_gh_repo()}/{_gh_branch()}/{root}/latest.json"
        r = requests.get(url, timeout=20)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def _cached_list_all_xlsx(path: str, ttl: int = 300) -> List[str]:
    key = "_cache_list_all_xlsx"
    now = time.time()
    cache = st.session_state.get(key, {})
    entry = cache.get(path)
    if entry and (now - entry["ts"] < ttl):
        return entry["data"]
    data = _list_all_xlsx(path)
    cache[path] = {"ts": now, "data": data}
    st.session_state[key] = cache
    return data

def load_latest_snapshot_df() -> Optional[pd.DataFrame]:
    # tenta pegar o mais recente via API listagem (mantém sem expor paths)
    try:
        all_files = _cached_list_all_xlsx(_gh_root(), ttl=300)
        if not all_files: return None
        all_files.sort(reverse=True)
        latest = all_files[0]
        raw = f"https://raw.githubusercontent.com/{_gh_repo()}/{_gh_branch()}/{latest}"
        df = pd.read_excel(raw)
        keep = ["site_nome","data","status","observacao","validador","data_validacao"]
        df = df[[c for c in keep if c in df.columns]].copy()
        df["data"]           = pd.to_datetime(df["data"], errors="coerce").dt.date
        df["data_validacao"] = pd.to_datetime(df.get("data_validacao", pd.NaT), errors="coerce")
        df["observacao"]     = df.get("observacao","").astype(str)
        df["validador"]      = df.get("validador","").astype(str)
        df["status"]         = df.get("status","Pendente").astype(str)
        df["yyyymm"]         = pd.to_datetime(df["data"]).dt.strftime("%Y-%m")
        return df.sort_values(["data","site_nome"]).reset_index(drop=True)
    except Exception:
        return None

# ============================================================================
# AUTO-LOAD ESTADO
# ============================================================================
if "df_validado" not in st.session_state:
    with st.spinner("Carregando dados..."):
        st.session_state.df_validado = load_latest_snapshot_df()
        st.session_state.ultimo_meta = load_latest_meta()

# Inicializa o carimbo local a partir do latest.json (se ainda não houver)
if "ultimo_meta" in st.session_state and st.session_state.ultimo_meta and "__last_saved_ts" not in st.session_state:
    st.session_state["__last_saved_ts"] = st.session_state.ultimo_meta.get("saved_at_utc")

if st.session_state.df_validado is None or st.session_state.df_validado.empty:
    st.info("Nenhum snapshot encontrado no GitHub. Salve ao menos um arquivo em data/validado/.")
    st.stop()

dfv = st.session_state.df_validado

# ============================================================================
# HELPERS
# ============================================================================
PT_MESES = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
def mes_label_pt(yyyymm: str) -> str:
    y, m = yyyymm.split("-"); return f"{PT_MESES[int(m)-1].capitalize()} de {y}"

# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.success(f"Logado como: {st.session_state.get('name') or st.session_state.get('username') or st.session_state.get('user')}")
    if st.button("Sair", use_container_width=True):
        st.session_state.clear()
        st.switch_page("app.py")
    st.markdown("---")

    st.header("📚 Módulo")
    st.page_link("pages/2_Geoportal.py", label="🗺️ Geoportal")
    st.markdown(
        """
<div style="margin-top:10px;background:#eef6f9;padding:12px 14px;border-radius:10px;
  font-size:.95rem;color:#0a4b68;font-weight:600;display:flex;align-items:center;border:1px solid #d7ecf3;">
  📍 Módulo ativo:&nbsp;<span>Cronograma de Passes de Satélites</span>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.header("Filtros")
    sites = sorted(dfv["site_nome"].dropna().unique())
    sel_sites = st.multiselect("Sites", options=sites, default=sites)

    meses = sorted(dfv["yyyymm"].dropna().unique())
    mes_default = st.session_state.get("mes_ano") or (meses[-1] if meses else None)
    idx = max(0, meses.index(mes_default)) if (mes_default in meses) else len(meses)-1
    mes_ano = st.selectbox("Mês", options=meses, index=idx)
    st.session_state["mes_ano"] = mes_ano

    autor_atual = st.text_input("Seu nome (autor do commit)", value=st.session_state.get("usuario_logado","")).strip()
    st.session_state["usuario_logado"] = autor_atual or "—"

# ============================================================================
# APP BAR (status + última atualização, priorizando salvamento local)
# ============================================================================
gh_ok = _ping_github()
badge = (
    '<span class="status-badge status-ok">🟢 Conexão OK</span>'
    if gh_ok else
    '<span class="status-badge status-err">🔴 Sem conexão</span>'
)

last_local = st.session_state.get("__last_saved_ts")  # ISO '...Z'
last_git   = (st.session_state.get("ultimo_meta") or {}).get("saved_at_utc")

def _fmt(ts: str) -> str:
    return ts.replace("T", " ").replace("Z", " UTC")

if last_local:
    stamp = _fmt(last_local)
elif last_git:
    stamp = _fmt(last_git)
else:
    stamp = "—"

meta_html = f"Última atualização em: {stamp}"

st.markdown(
    f"""
<div class="appbar"><div class="appbar-inner">
  <div><h1>Calendário de Validação</h1><div class="meta">{meta_html}</div></div>
  <div>{badge}</div>
</div></div>
""",
    unsafe_allow_html=True,
)

# Mensagem pós-salvamento (sem path)
if st.session_state.get("__last_save_ok"):
    st.success(st.session_state.pop("__last_save_ok"))

# ============================================================================
# DADOS FILTRADOS
# ============================================================================
mask = dfv["site_nome"].isin(sel_sites) & (dfv["yyyymm"] == mes_ano)
fdf = dfv.loc[mask].copy().sort_values(["data","site_nome"])
label_mes = mes_label_pt(mes_ano)

# ============================================================================
# CARD: TABELA (STATUS com cores via rótulos)
# ============================================================================
st.markdown(f'<div class="card"><h3>📋 Tabela de passagens — {label_mes}</h3>', unsafe_allow_html=True)

# Mapeamentos visual <-> valor real
STATUS_TO_VIS = {
    "Pendente": "⚫ Pendente",
    "Aprovada": "🟢 Aprovada",
    "Rejeitada": "🔴 Rejeitada",
}
VIS_TO_STATUS = {v: k for k, v in STATUS_TO_VIS.items()}
VIS_OPTIONS = ["⚫ Pendente", "🟢 Aprovada", "🔴 Rejeitada"]

# View exibida/edição
view = fdf[["site_nome","data","status","observacao","validador","data_validacao"]].copy()
view["data"] = pd.to_datetime(view["data"]).dt.strftime("%Y-%m-%d")
view["observacao"] = view["observacao"].astype("string")
view["validador"] = view["validador"].astype("string")
view["data_validacao"] = view["data_validacao"].apply(
    lambda x: "" if pd.isna(x) else pd.to_datetime(x).strftime("%Y-%m-%d %H:%M:%S")
).astype("string")

# Coluna visual para o Status (com ícones coloridos)
view["Status"] = view["status"].map(STATUS_TO_VIS).fillna("⚫ Pendente")
view = view.drop(columns=["status"])  # escondemos a crua

colcfg = {
    "site_nome": st.column_config.TextColumn("Site", disabled=True, width="medium"),
    "data": st.column_config.TextColumn("Data", disabled=True, width="small"),
    "Status": st.column_config.SelectboxColumn(
        "Status", options=VIS_OPTIONS, required=True, width="small"
    ),
    "observacao": st.column_config.TextColumn("Observação", width="medium"),
    "validador": st.column_config.TextColumn("Validador", width="small"),
    "data_validacao": st.column_config.TextColumn("Data validação", disabled=True, width="medium"),
}

editor_key = f"ed_{mes_ano}_{abs(hash(tuple(sel_sites)))%100000}"
edited = st.data_editor(
    view,
    num_rows="fixed",
    width='stretch',
    column_config=colcfg,
    disabled=["site_nome","data","data_validacao"],
    key=editor_key,
)

st.markdown("</div>", unsafe_allow_html=True)

# ============================================================================
# DETECTA ALTERAÇÕES (comparando já mapeado para status real)
# ============================================================================
def _normalize_for_compare(df_disp: pd.DataFrame) -> pd.DataFrame:
    df = df_disp.copy()
    df["status"] = df["Status"].map(VIS_TO_STATUS).fillna("Pendente")
    return df[["site_nome","data","status","observacao","validador"]]

def _unsaved_mask(orig_display: pd.DataFrame, ed_display: pd.DataFrame) -> pd.Series:
    a = _normalize_for_compare(orig_display)
    b = _normalize_for_compare(ed_display)
    return (a.values != b.values).any(axis=1)

changed_mask = _unsaved_mask(view, edited)
unsaved = int(changed_mask.sum())
if unsaved > 0:
    st.markdown(f'<div class="unsaved"><strong>{unsaved}</strong> alteração(ões) não salvas.</div>', unsafe_allow_html=True)

# ============================================================================
# SALVAR (sem expor path) + atualiza "última atualização"
# ============================================================================
def _exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    cols = ["site_nome","data","status","observacao","validador","data_validacao"]
    out = df[cols].copy()
    out["data"] = pd.to_datetime(out["data"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    dv = pd.to_datetime(out["data_validacao"], errors="coerce")
    out["data_validacao"] = dv.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        out.to_excel(writer, index=False, sheet_name="validacao")
    buf.seek(0); return buf.read()

def _aplicar_salvamento(edited_display: pd.DataFrame):
    base = st.session_state.df_validado.copy()
    e = edited_display.copy()

    # Converte de volta para o status real e data
    e["status"] = e["Status"].map(VIS_TO_STATUS).fillna("Pendente")
    e["data"] = pd.to_datetime(e["data"]).dt.date

    keys = ["site_nome","data"]
    upd_cols = ["status","observacao","validador"]

    merged = base.merge(e[keys + upd_cols], on=keys, how="left", suffixes=("", "_novo"))
    for c in upd_cols:
        c_new = f"{c}_novo"
        if c_new in merged.columns:
            mask_upd = ~merged[c_new].isna()
            merged.loc[mask_upd, c] = merged.loc[mask_upd, c_new]
            merged.drop(columns=[c_new], inplace=True, errors="ignore")

    mudou = merged["status"].isin(["Aprovada","Rejeitada"]) & merged["data_validacao"].isna()
    ts_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    merged.loc[mudou, "data_validacao"] = ts_now

    st.session_state.df_validado = merged
    try:
        xlsb = _exportar_excel_bytes(merged)
        meta = gh_save_snapshot(xlsb, author=st.session_state.get("usuario_logado",""))
        st.session_state.ultimo_meta = meta
        # carimbo local = horário retornado
        st.session_state["__last_saved_ts"] = meta.get("saved_at_utc")
        stamp = meta.get("saved_at_utc","").replace("T"," ").replace("Z"," UTC")
        st.session_state["__last_save_ok"] = f"Última atualização em {stamp}"
    except Exception:
        # sem publish: registra agora (UTC) como carimbo local
        now_utc = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")
        st.session_state["__last_saved_ts"] = now_utc
        st.session_state["__last_save_ok"] = "Atualização local concluída. Publicação remota indisponível."
    _rerun()

save_clicked = st.button("💾 Salvar alterações", type="primary", disabled=(unsaved == 0))
if save_clicked:
    _aplicar_salvamento(edited)

# ============================================================================
# CARD: AÇÕES EM LOTE + CALENDÁRIO
# ============================================================================
st.markdown(f'<div class="card"><h3>⚙️ Ações em lote por dia — {label_mes}</h3>', unsafe_allow_html=True)

dias_disponiveis = sorted(pd.to_datetime(fdf["data"]).dt.date.unique())
if dias_disponiveis:
    d_sel = st.selectbox("Dia", options=dias_disponiveis, format_func=lambda d: d.strftime("%Y-%m-%d"))
    cA, cB, _ = st.columns([1,1,6])

    def _lote(status_final: str, msg_ok: str):
        base = st.session_state.df_validado
        idx = (pd.to_datetime(base["data"]).dt.date == d_sel) & base["site_nome"].isin(sel_sites) & (base["yyyymm"] == mes_ano)
        base.loc[idx, "status"] = status_final
        ts_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        base.loc[idx & base["data_validacao"].isna(), "data_validacao"] = ts_now
        st.session_state.df_validado = base
        try:
            xlsb = _exportar_excel_bytes(base)
            meta = gh_save_snapshot(xlsb, author=st.session_state.get("usuario_logado",""))
            st.session_state.ultimo_meta = meta
            st.session_state["__last_saved_ts"] = meta.get("saved_at_utc")
            stamp = meta.get("saved_at_utc","").replace("T"," ").replace("Z"," UTC")
            st.session_state["__last_save_ok"] = f"{msg_ok} em {d_sel}. Última atualização em {stamp}"
        except Exception:
            now_utc = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")
            st.session_state["__last_saved_ts"] = now_utc
            st.session_state["__last_save_ok"] = f"{msg_ok} em {d_sel}. Publicação remota indisponível."
        _rerun()

    with cA:
        if st.button("✅ Aprovar tudo do dia"): _lote("Aprovada", "Aprovado tudo")
    with cB:
        if st.button("⛔ Rejeitar tudo do dia"): _lote("Rejeitada", "Rejeitado tudo")
else:
    st.caption("Sem passagens no mês/site(s) filtrados.")

# ---- Calendário -------------------------------------------------------------
def montar_calendario(df_mes: pd.DataFrame, mes_ano: str,
                      only_color_with_events: bool = True,
                      show_badges: bool = True) -> go.Figure:
    primeiro = pd.to_datetime(f"{mes_ano}-01")
    ultimo = (primeiro + pd.offsets.MonthEnd(1))
    dias = pd.date_range(primeiro, ultimo, freq="D")

    if df_mes.empty:
        agg = pd.DataFrame(columns=["data","aprovadas","rejeitadas","pendentes","sites"])
    else:
        agg = (df_mes.assign(data=pd.to_datetime(df_mes["data"]).dt.date)
                     .groupby("data")
                     .agg(aprovadas=("status", lambda s: (s == "Aprovada").sum()),
                          rejeitadas=("status", lambda s: (s == "Rejeitada").sum()),
                          pendentes=("status", lambda s: (s == "Pendente").sum()),
                          sites=("site_nome", lambda s: sorted(set(s))))
                     .reset_index())
    info_map = {row["data"]: row for _, row in agg.iterrows()}

    def cor_do_dia(d: pd.Timestamp) -> str:
        inf = info_map.get(d.date())
        if inf is None:
            return "#ECEFF1" if only_color_with_events else "#B0BEC5"
        if inf["rejeitadas"] > 0: return "#c62828"
        if inf["pendentes"] > 0 and inf["aprovadas"] == 0: return "#B0BEC5"
        return "#2e7d32"

    def weekday_dom(d: pd.Timestamp) -> int:
        return (d.weekday() + 1) % 7  # domingo = 0

    grid = np.full((6, 7), None, dtype=object)
    week = 0
    for d in dias:
        col = weekday_dom(d)
        if col == 0 and d.day != 1:
            week += 1
        grid[week, col] = d

    fig = go.Figure()
    for r in range(6):
        for c in range(7):
            d = grid[r, c]
            if d is None: 
                continue
            fill = cor_do_dia(d)
            fig.add_shape(type="rect", x0=c, x1=c+1, y0=5-r, y1=6-r,
                          line=dict(width=1, color="#90A4AE"), fillcolor=fill)
            fig.add_annotation(x=c+0.05, y=5-r+0.85, text=str(d.day),
                               showarrow=False, xanchor="left", yanchor="top", font=dict(size=12))
            inf = info_map.get(d.date())
            if show_badges and (inf is not None):
                y0 = 5-r+0.18; badges = []
                if inf["aprovadas"] > 0: badges.append(("●", "#2e7d32"))
                if inf["rejeitadas"] > 0: badges.append(("●", "#c62828"))
                if inf["pendentes"] > 0: badges.append(("●", "#607D8B"))
                x0 = c+0.08
                for ch, colr in badges:
                    fig.add_annotation(x=x0, y=y0, text=f"<span style='color:{colr}'>{ch}</span>",
                                       showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=12))
                    x0 += 0.12
                txt_cnt = f"{inf['aprovadas']}A/{inf['rejeitadas']}R/{inf['pendentes']}P"
                fig.add_annotation(x=c+0.95, y=5-r+0.18, text=txt_cnt,
                                   showarrow=False, xanchor="right", yanchor="bottom", font=dict(size=10))
            if inf is not None:
                sites_txt = ", ".join(inf["sites"]) if inf["sites"] else "-"
                hover = (f"{d.strftime('%Y-%m-%d')}<br>"
                         f"Aprovadas: {inf['aprovadas']} | Rejeitadas: {inf['rejeitadas']} | Pendentes: {inf['pendentes']}<br>"
                         f"Sites: {sites_txt}")
                fig.add_trace(go.Scatter(x=[c+0.5], y=[5-r+0.5], mode="markers",
                                         marker=dict(size=1, color="rgba(0,0,0,0)"),
                                         hovertemplate=hover, showlegend=False))
    fig.update_xaxes(visible=False); fig.update_yaxes(visible=False)
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=10),
                      paper_bgcolor="white", plot_bgcolor="white")
    return fig

st.subheader(f"Calendário do mês selecionado — {label_mes}")
fig = montar_calendario(fdf, mes_ano, only_color_with_events=True, show_badges=True)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown("</div>", unsafe_allow_html=True)  # fecha card
