# -*- coding: utf-8 -*-
# pages/4_Agendamento_de_Imagens.py
# UX estilo SaaS + Sidebar fixa + contornos visíveis nos filtros
# Compat Streamlit (st.rerun / experimental), ações em lote, calendário
# GitHub com token + fallback via latest.json + cache simples
# Correção de merge/salvamento (evita KeyError) e uso de openpyxl

from __future__ import annotations

import io
import json
import time
import base64
import datetime as dt
from pathlib import Path
from typing import Optional, List, Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ============================================================================
# CONFIG PÁGINA
# ============================================================================
st.set_page_config(
    page_title="🛰️ Agendamento de Imagens",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar fixa/visível + UI estilo SaaS + chips com contorno visível ---
st.markdown("""
<style>
/* Remove o botão de colapso (hamburger) */
div[data-testid="collapsedControl"] { display: none !important; }

/* Força a sidebar aberta, fixa e com altura total */
section[data-testid="stSidebar"], aside[data-testid="stSidebar"] {
  visibility: visible !important;
  transform: translateX(0) !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  width: 300px !important;
  min-width: 300px !important;
  background: #ffffff !important;
  border-right: 1px solid #eef0f3 !important;
  position: sticky !important;
  top: 0 !important;
  height: 100vh !important;
  overflow: auto !important;
  z-index: 100;
}

/* Esconde a navegação automática da sidebar (se usa page_link manual) */
div[data-testid="stSidebarNav"] { display: none !important; }

/* Ajustes do conteúdo principal */
.reportview-container .main .block-container {max-width: 1320px; padding-top: .6rem; padding-bottom: 4rem;}

/* App bar */
.appbar {position: sticky; top: 0; z-index: 50; background:#ffffffcc; backdrop-filter: blur(8px);
  border-bottom:1px solid #eef0f3; margin-bottom:8px;}
.appbar-inner {display:flex; align-items:center; justify-content:space-between; padding:10px 0;}
.appbar h1 {font-size:1.6rem; margin:0;}
.appbar .meta {color:#6b7280; font-size:.9rem;}

/* Cards */
.card {background:#fff; border:1px solid #eef0f3; border-radius:16px;
  box-shadow:0 1px 2px rgba(16,24,40,.04); padding:16px; margin:12px 0;}
.card h3 {margin:0 0 8px 0; font-size:1.1rem}

/* Botões */
.btn-primary {background:#1f6feb; border:1px solid #1f6feb; color:#fff;
  border-radius:10px; padding:8px 14px; font-weight:600;}
.btn-ghost {background:#fff; border:1px solid #e5e7eb; color:#111827;
  border-radius:10px; padding:8px 14px; font-weight:600;}

/* Badges */
.badge{display:inline-flex; align-items:center; padding:2px 8px; border-radius:999px;
  font-size:12px; font-weight:600; vertical-align:middle;}
.badge-pendente{background:#fff7ed; color:#b45309; border:1px solid #fed7aa;}
.badge-aprovado{background:#ecfdf5; color:#166534; border:1px solid #bbf7d0;}
.badge-rejeitado{background:#fef2f2; color:#991b1b; border:1px solid #fecaca;}

/* Tabela: cabeçalho sticky */
[data-testid="stTable"] thead tr {position: sticky; top: 48px; background:#fff; z-index:5; box-shadow:0 1px 0 #eef0f3;}

/* Barra de aviso */
.unsaved {background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:10px 14px;
  box-shadow:0 8px 24px rgba(16,24,40,.12); display:flex; gap:10px; align-items:center;}

/* Esconde header padrão do Streamlit */
header[data-testid="stHeader"]{ display:none !important; }

/* ===== Sidebar: inputs/chips com contornos visíveis ===== */
section[data-testid="stSidebar"] {
  --sb-border: #d1d5db;         /* cinza da borda */
  --sb-border-strong: #9ca3af;  /* hover */
  --sb-bg: #fafafa;             /* fundo do campo */
  --sb-bg-focus: #ffffff;       /* foco */
  --sb-focus-ring: rgba(31,111,235,.18); /* anel de foco azul */
}
/* Caixa do Select/MultiSelect */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
  border: 1.5px solid var(--sb-border) !important;
  background: var(--sb-bg) !important;
  border-radius: 10px !important;
  transition: border-color .15s ease, box-shadow .15s ease, background .15s ease;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover {
  border-color: var(--sb-border-strong) !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within {
  border-color: #1f6feb !important;
  background: var(--sb-bg-focus) !important;
  box-shadow: 0 0 0 3px var(--sb-focus-ring) !important;
}
/* Chips (tags) do MultiSelect */
section[data-testid="stSidebar"] div[data-baseweb="tag"] {
  background: #ffffff !important;
  color: #111827 !important;
  border: 1.2px solid var(--sb-border) !important;
  box-shadow: 0 1px 0 rgba(0,0,0,.04) !important;
  border-radius: 10px !important;
}
section[data-testid="stSidebar"] div[data-baseweb="tag"]:hover {
  border-color: var(--sb-border-strong) !important;
}
/* Ícone de fechar do chip */
section[data-testid="stSidebar"] div[data-baseweb="tag"] svg {
  fill: #6b7280 !important;
}
section[data-testid="stSidebar"] div[data-baseweb="tag"]:hover svg {
  fill: #374151 !important;
}
/* Títulos da sidebar */
section[data-testid="stSidebar"] h2, 
section[data-testid="stSidebar"] h3 {
  color: #111827 !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# Função de RERUN compatível (novo e antigo Streamlit)
# ============================================================================
def _rerun():
    """Compat: usa st.rerun() (novo) ou st.experimental_rerun() (antigo)."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ============================================================================
# LOGO FIXO SUPERIOR DIREITO (opcional)
# ============================================================================
def _logo_b64_from(path: str) -> Optional[str]:
    p = Path(path)
    if not p.exists(): return None
    try:
        return base64.b64encode(p.read_bytes()).decode("utf-8")
    except Exception:
        return None

_LOGO_B64 = _logo_b64_from("logomavipe.jpeg")
if _LOGO_B64:
    st.markdown(f"""
    <div style="position:fixed;top:12px;right:20px;z-index:9999;pointer-events:none">
      <img src="data:image/jpeg;base64,{_LOGO_B64}" style="height:100px;width:auto;opacity:.98"/>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# GITHUB – utilitários (com token + fallback e cache simples)
# ============================================================================
def _gh_headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = st.secrets.get("github_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def _gh_repo():   return st.secrets["github_repo"]
def _gh_branch(): return st.secrets.get("github_branch", "main")
def _gh_root():   return st.secrets.get("gh_data_root", "data/validado")

def _list_contents(path: str):
    """Lista itens usando a API com token (evita 403)."""
    url = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}?ref={_gh_branch()}"
    r = requests.get(url, headers=_gh_headers(), timeout=20)
    if r.status_code == 403 and "rate limit" in r.text.lower():
        raise RuntimeError("GitHub rate limit exceeded ao listar conteúdos")
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
    payload = {"message": message,
               "content": base64.b64encode(content_bytes).decode("utf-8"),
               "branch": _gh_branch()}
    if sha: payload["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Falha ao salvar no GitHub ({r.status_code}): {r.text}")
    return r.json()

def gh_save_snapshot(xls_bytes: bytes, author: Optional[str] = None) -> dict:
    root = _gh_root().rstrip("/")
    now  = dt.datetime.now(dt.timezone.utc)
    yyyy = now.strftime("%Y"); mm = now.strftime("%m"); stamp = now.strftime("%Y%m%d-%H%M%S")
    excel_rel_path = f"{root}/{yyyy}/{mm}/validado-{stamp}.xlsx"
    gh_put_file(excel_rel_path, xls_bytes, f"[streamlit] snapshot {stamp} (autor={author or 'anon'})", None)
    latest = {"saved_at_utc": now.isoformat().replace("+00:00","Z"),
              "author": author or "", "path": excel_rel_path}
    latest_path = f"{root}/latest.json"
    sha_old = gh_get_file_sha(latest_path)
    gh_put_file(latest_path, json.dumps(latest, ensure_ascii=False, indent=2).encode("utf-8"),
                f"[streamlit] update latest -> {excel_rel_path}", sha_old)
    return latest

def load_latest_meta() -> Optional[dict]:
    """Lê latest.json via raw (não usa API, menor chance de 403)."""
    try:
        root = _gh_root().rstrip("/")
        url = f"https://raw.githubusercontent.com/{_gh_repo()}/{_gh_branch()}/{root}/latest.json"
        r = requests.get(url, timeout=20)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

# cache simples em memória pra reduzir chamadas à API
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
    """1) tenta via latest.json (raw); 2) fallback: lista via API com token + cache."""
    # 1) pelo latest.json
    try:
        meta = load_latest_meta()
        if meta and meta.get("path"):
            raw = f"https://raw.githubusercontent.com/{_gh_repo()}/{_gh_branch()}/{meta['path']}"
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
    except Exception as e:
        st.warning(f"Falhou ao baixar pelo latest.json: {e}")

    # 2) fallback: lista via API (com token + cache)
    try:
        all_files = _cached_list_all_xlsx(_gh_root(), ttl=300)
        if not all_files:
            return None
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
    except Exception as e:
        st.warning(f"Não consegui listar via API do GitHub: {e}")
        return None

# ============================================================================
# AUTO-LOAD ESTADO
# ============================================================================
if "df_validado" not in st.session_state:
    with st.spinner("Carregando último arquivo salvo no GitHub..."):
        st.session_state.df_validado = load_latest_snapshot_df()
        st.session_state.ultimo_meta = load_latest_meta()

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

SUPPORT_MD = hasattr(st.column_config, "MarkdownColumn")

def badge_html(status: str) -> str:
    s = (status or "").lower()
    if "aprova" in s: return '<span class="badge badge-aprovado">Aprovada</span>'
    if "rejei"  in s: return '<span class="badge badge-rejeitado">Rejeitada</span>'
    return '<span class="badge badge-pendente">Pendente</span>'

def badge_plain(status: str) -> str:
    s = (status or "").lower()
    if "aprova" in s: return "Aprovada ✅"
    if "rejei"  in s: return "Rejeitada ⛔"
    return "Pendente ⌛"

# ============================================================================
# SIDEBAR (conteúdo)
# ============================================================================
with st.sidebar:
    st.header("📚 Módulos")
    st.page_link("pages/2_Geoportal.py", label="🗺️ Geoportal")
    st.page_link("pages/1_Estatisticas_Gerais.py", label="📊 Estatísticas gerais")
    st.page_link("pages/3_Relatorio_OGMP_2_0.py", label="📄 Relatório OGMP 2.0")
    st.page_link("pages/4_Agendamento_de_Imagens.py", label="🛰️ Agendamento de imagens", disabled=True)

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
# APP BAR
# ============================================================================
meta_html = ""
if st.session_state.ultimo_meta:
    meta = st.session_state.ultimo_meta
    meta_html = f'Último autor: {meta.get("author","—")} · Salvo (UTC): {meta.get("saved_at_utc","")} · <code>{meta.get("path","")}</code>'

st.markdown(f"""
<div class="appbar"><div class="appbar-inner">
  <div><h1>Calendário de Validação</h1><div class="meta">{meta_html}</div></div>
  <div class="actions"></div>
</div></div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns([6,1,1])
with c2:
    if st.button("Atualizar", use_container_width=True):
        st.session_state.df_validado = load_latest_snapshot_df()
        st.session_state.ultimo_meta = load_latest_meta()
        _rerun()
with c3:
    save_clicked_top = st.button("💾 Salvar alterações", type="primary", use_container_width=True)

# ============================================================================
# DADOS FILTRADOS
# ============================================================================
mask = dfv["site_nome"].isin(sel_sites) & (dfv["yyyymm"] == mes_ano)
fdf = dfv.loc[mask].copy().sort_values(["data","site_nome"])
label_mes = mes_label_pt(mes_ano)

# ============================================================================
# CARD: TABELA
# ============================================================================
st.markdown(f'<div class="card"><h3>📋 Tabela de passagens — {label_mes}</h3>', unsafe_allow_html=True)

view = fdf[["site_nome","data","status","observacao","validador","data_validacao"]].copy()
view["data"] = pd.to_datetime(view["data"]).dt.strftime("%Y-%m-%d")
view["observacao"] = view["observacao"].astype("string")
view["validador"] = view["validador"].astype("string")
view["data_validacao"] = view["data_validacao"].apply(
    lambda x: "" if pd.isna(x) else pd.to_datetime(x).strftime("%Y-%m-%d %H:%M:%S")
).astype("string")
view["status_badge"] = view["status"].map(badge_html if SUPPORT_MD else badge_plain)

colcfg = {
    "site_nome": st.column_config.TextColumn("Site", disabled=True, width="medium"),
    "data": st.column_config.TextColumn("Data", disabled=True, width="small"),
    "status": st.column_config.SelectboxColumn(
        "Alterar status",
        options=["Pendente","Aprovada","Rejeitada"],
        required=True,
        width="small"
    ),
    "observacao": st.column_config.TextColumn("Observação", width="medium"),
    "validador": st.column_config.TextColumn("Validador", width="small"),
    "data_validacao": st.column_config.TextColumn("Data validação", disabled=True, width="medium"),
}
if SUPPORT_MD:
    colcfg["status_badge"] = st.column_config.MarkdownColumn("Status", help="Estado atual", width="small")
else:
    colcfg["status_badge"] = st.column_config.TextColumn("Status", disabled=True, width="small")

edited = st.data_editor(
    view,
    num_rows="fixed",
    width='stretch',
    column_config=colcfg,
    disabled=["site_nome","data","status_badge","data_validacao"],
    key="editor_agnd_final",
)

st.markdown("</div>", unsafe_allow_html=True)

# ============================================================================
# CONTADOR DE ALTERAÇÕES (visual)
# ============================================================================
def _unsaved_count(orig: pd.DataFrame, ed: pd.DataFrame) -> int:
    a = orig[["site_nome","data","status","observacao","validador"]].copy()
    b = ed[["site_nome","data","status","observacao","validador"]].copy()
    return int((a.values != b.values).any(axis=1).sum())

unsaved = _unsaved_count(view, edited)
if unsaved > 0:
    st.markdown(f'<div class="unsaved"><strong>{unsaved}</strong> alteração(ões) não salvas.</div>', unsafe_allow_html=True)

# ============================================================================
# SALVAR (GitHub) — corrigido para evitar KeyError
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

def _aplicar_salvamento(edited_df: pd.DataFrame):
    base = st.session_state.df_validado.copy()
    e = edited_df.copy()
    e["data"] = pd.to_datetime(e["data"]).dt.date

    keys = ["site_nome","data"]
    upd_cols = ["status","observacao","validador"]

    # NÃO removemos colunas do base; garantimos sufixos para TODOS os campos
    merged = base.merge(e[keys + upd_cols], on=keys, how="left", suffixes=("", "_novo"))

    # aplica valor de *_novo quando existir e não for NaN
    for c in upd_cols:
        c_new = f"{c}_novo"
        if c_new in merged.columns:
            mask_upd = ~merged[c_new].isna()
            merged.loc[mask_upd, c] = merged.loc[mask_upd, c_new]
            merged.drop(columns=[c_new], inplace=True, errors="ignore")

    # marca data_validacao quando vira Aprovada/Rejeitada e estava vazia
    mudou = merged["status"].isin(["Aprovada","Rejeitada"]) & merged["data_validacao"].isna()
    ts_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    merged.loc[mudou, "data_validacao"] = ts_now

    st.session_state.df_validado = merged
    st.success("Alterações salvas localmente.")

    try:
        xlsb = _exportar_excel_bytes(merged)
        meta = gh_save_snapshot(xlsb, author=st.session_state.get("usuario_logado",""))
        st.session_state.ultimo_meta = meta
        st.info(f"Publicado no GitHub: `{meta['path']}` (UTC: {meta['saved_at_utc']})")
    except Exception as e:
        st.warning(f"Salvou localmente, mas falhou ao publicar no GitHub: {e}")

save_clicked_bottom = st.button("💾 Salvar alterações")
if save_clicked_top or save_clicked_bottom:
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
        st.success(f"{msg_ok} em {d_sel}.")
        try:
            xlsb = _exportar_excel_bytes(base)
            meta = gh_save_snapshot(xlsb, author=st.session_state.get("usuario_logado",""))
            st.session_state.ultimo_meta = meta
            st.info(f"Publicado no GitHub: `{meta['path']}`")
        except Exception as e:
            st.warning(f"Falhou ao publicar no GitHub: {e}")

    with cA:
        if st.button("✅ Aprovar tudo do dia"):
            _lote("Aprovada", "Aprovado tudo")
    with cB:
        if st.button("⛔ Rejeitar tudo do dia"):
            _lote("Rejeitada", "Rejeitado tudo")
else:
    st.caption("Sem passagens no mês/site(s) filtrados.")

# Calendário
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
            if d is None: continue
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

# ============================================================================
# CARD: EXPORTAR / DIAGNÓSTICO
# ============================================================================
st.markdown('<div class="card"><h3>⬇️ Exportar arquivo validado</h3>', unsafe_allow_html=True)
colA, colB = st.columns([1,2])
with colA:
    nome_arquivo = st.text_input("Nome do arquivo", value="passagens_validado.xlsx")
with colB:
    xlsb = _exportar_excel_bytes(st.session_state.df_validado)
    st.download_button("Baixar Excel validado", data=xlsb, file_name=nome_arquivo,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
st.markdown("</div>", unsafe_allow_html=True)

with st.expander("🔧 Diagnóstico GitHub", expanded=False):
    has_token  = "github_token"  in st.secrets
    has_repo   = "github_repo"   in st.secrets
    has_branch = "github_branch" in st.secrets
    has_root   = "gh_data_root"  in st.secrets
    st.write("Secrets:", {"github_token": has_token, "github_repo": has_repo,
                          "github_branch": has_branch, "gh_data_root": has_root})
    if has_repo:   st.write("Repo:", st.secrets["github_repo"])
    if has_branch: st.write("Branch:", st.secrets["github_branch"])
    if has_root:   st.write("Raiz:", st.secrets["gh_data_root"])
    if st.button("🔄 Recarregar último snapshot do GitHub"):
        st.session_state.df_validado = load_latest_snapshot_df()
        st.session_state.ultimo_meta = load_latest_meta()
        _rerun()

