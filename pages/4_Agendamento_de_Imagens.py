# -*- coding: utf-8 -*-
# pages/4_Agendamento_de_Imagens.py
# Calendário + validação (sim/não) + GitHub + Auto-load + Último Autor
from __future__ import annotations

import io
import base64
import json
import datetime as dt
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# CONFIG DE PÁGINA (sidebar sempre expandida e sem botão de recolher)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="🛰️ Agendamento de Imagens (Validação)",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      /* Esconde o botão de recolher a sidebar */
      div[data-testid="collapsedControl"]{ display:none !important; }
      /* Mantém a sidebar visível, sem nav nativo (opcional) */
      section[data-testid="stSidebar"] nav, div[data-testid="stSidebarNav"]{ display:none!important; }
      /* Títulos um pouco mais compactos */
      .block-container{ padding-top: .6rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES (GitHub)
# -----------------------------------------------------------------------------
def _gh_headers():
    return {
        "Authorization": f"Bearer {st.secrets['github_token']}",
        "Accept": "application/vnd.github+json",
    }

def _gh_repo():   return st.secrets["github_repo"]
def _gh_branch(): return st.secrets.get("github_branch", "main")
def _gh_root():   return st.secrets.get("gh_data_root", "data/validado")

def _list_contents(path: str):
    url = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}?ref={_gh_branch()}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def _list_all_xlsx(path: str) -> List[str]:
    items = _list_contents(path)
    files = []
    for it in items:
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
    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": _gh_branch(),
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Falha ao salvar no GitHub ({r.status_code}): {r.text}")
    return r.json()

def gh_save_snapshot(xls_bytes: bytes, author: Optional[str] = None) -> dict:
    root = _gh_root()
    now  = dt.datetime.now(dt.timezone.utc)
    yyyy = now.strftime("%Y")
    mm   = now.strftime("%m")
    stamp = now.strftime("%Y%m%d-%H%M%S")
    excel_rel_path = f"{root}/{yyyy}/{mm}/validado-{stamp}.xlsx"
    gh_put_file(
        excel_rel_path,
        xls_bytes,
        f"[streamlit] snapshot {stamp} (autor={author or 'anon'})",
        None,
    )
    latest = {"saved_at_utc": now.isoformat().replace("+00:00", "Z"),
              "author": author or "", "path": excel_rel_path}
    latest_path = f"{root}/latest.json"
    sha_old = gh_get_file_sha(latest_path)
    gh_put_file(
        latest_path,
        json.dumps(latest, ensure_ascii=False, indent=2).encode("utf-8"),
        f"[streamlit] update latest -> {excel_rel_path}",
        sha_old,
    )
    return latest

def load_latest_meta() -> Optional[dict]:
    try:
        root = _gh_root().rstrip("/")
        url = f"https://raw.githubusercontent.com/{_gh_repo()}/{_gh_branch()}/{root}/latest.json"
        r = requests.get(url, timeout=20)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def load_latest_snapshot_df() -> Optional[pd.DataFrame]:
    try:
        all_files = _list_all_xlsx(_gh_root())
        if not all_files:
            return None
        all_files.sort(reverse=True)
        latest = all_files[0]
        raw = f"https://raw.githubusercontent.com/{_gh_repo()}/{_gh_branch()}/{latest}"
        df = pd.read_excel(raw)
        keep = ["site_nome","data","status","observacao","validador","data_validacao"]
        df = df[[c for c in keep if c in df.columns]].copy()
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
        if "data_validacao" in df.columns:
            df["data_validacao"] = pd.to_datetime(df["data_validacao"], errors="coerce")
        else:
            df["data_validacao"] = pd.NaT
        df["observacao"] = df.get("observacao","").astype(str)
        df["validador"]  = df.get("validador","").astype(str)
        df["status"]     = df.get("status","Pendente").astype(str)
        df["yyyymm"] = pd.to_datetime(df["data"]).dt.strftime("%Y-%m")
        return df.sort_values(["data","site_nome"]).reset_index(drop=True)
    except Exception as e:
        st.warning(f"Não consegui carregar o último snapshot do GitHub: {e}")
        return None

# -----------------------------------------------------------------------------
# ESTADO / AUTO-LOAD
# -----------------------------------------------------------------------------
if "df_validado" not in st.session_state:
    with st.spinner("Carregando último arquivo salvo no GitHub..."):
        st.session_state.df_validado = load_latest_snapshot_df()
        st.session_state.ultimo_meta = load_latest_meta()

# -----------------------------------------------------------------------------
# SIDEBAR (links, filtros)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("📚 Módulos")
    st.page_link("pages/2_Geoportal.py", label="🗺️ Geoportal")
    st.page_link("pages/1_Estatisticas_Gerais.py", label="📊 Estatísticas gerais")
    st.page_link("pages/3_Relatorio_OGMP_2_0.py", label="📄 Relatório OGMP 2.0")
    st.page_link("pages/4_Agendamento_de_Imagens.py", label="🛰️ Agendamento de imagens", disabled=True)
    st.markdown("---")

    st.header("Filtros")
    if st.session_state.df_validado is None or st.session_state.df_validado.empty:
        st.info("Nenhum snapshot encontrado no GitHub. Salve ao menos um arquivo.")
        st.stop()

    dfv = st.session_state.df_validado
    sites = sorted(dfv["site_nome"].dropna().unique())
    sel_sites = st.multiselect("Sites", options=sites, default=sites)

    meses = sorted(dfv["yyyymm"].dropna().unique())
    # guarda seleção no session_state (NÃO usar st.sidebar.session_state)
    mes_default = st.session_state.get("mes_ano") or (meses[-1] if meses else None)
    mes_ano = st.selectbox("Mês", options=meses, index=max(0, meses.index(mes_default)) if mes_default in meses else len(meses)-1)
    st.session_state["mes_ano"] = mes_ano

    autor_atual = st.text_input("Seu nome (autor do commit)", value=st.session_state.get("usuario_logado","")).strip()
    st.session_state["usuario_logado"] = autor_atual or "—"

# -----------------------------------------------------------------------------
# HELPERS DE UI
# -----------------------------------------------------------------------------
PT_MESES = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
def mes_label_pt(mes_ano: str) -> str:
    # mes_ano = "YYYY-MM"
    y, m = mes_ano.split("-")
    nome = PT_MESES[int(m)-1].capitalize()
    return f"{nome} de {y}"

label_mes = mes_label_pt(mes_ano)

# -----------------------------------------------------------------------------
# TABELA EDITÁVEL (SIM / NÃO)
# -----------------------------------------------------------------------------
st.title("🛰️ Calendário de Validação")
if st.session_state.ultimo_meta:
    meta = st.session_state.ultimo_meta
    st.caption(f"**Último autor:** {meta.get('author','—')}  •  **Salvo (UTC):** {meta.get('saved_at_utc','')}  •  `{meta.get('path','')}`")

mask = dfv["site_nome"].isin(sel_sites) & (dfv["yyyymm"] == mes_ano)
fdf = dfv.loc[mask].copy().sort_values(["data","site_nome"])

st.subheader(f"📋 Tabela de passagens — {label_mes}")

view = fdf[["site_nome", "data", "status", "observacao", "validador", "data_validacao"]].copy()
view["data"] = pd.to_datetime(view["data"]).dt.strftime("%Y-%m-%d")
view["sim"] = (view["status"] == "Aprovada")
view["nao"] = (view["status"] == "Rejeitada")
view["observacao"] = view["observacao"].astype("string")
view["validador"] = view["validador"].astype("string")
view["data_validacao"] = view["data_validacao"].apply(
    lambda x: "" if pd.isna(x) else pd.to_datetime(x).strftime("%Y-%m-%d %H:%M:%S")
).astype("string")

edited = st.data_editor(
    view,
    num_rows="fixed",
    width='stretch',
    column_config={
        "sim": st.column_config.CheckboxColumn(label="Confirmar (sim)", help="Marca como Aprovada"),
        "nao": st.column_config.CheckboxColumn(label="Rejeitar (não)", help="Marca como Rejeitada"),
        "status": st.column_config.TextColumn(disabled=True),
        "data": st.column_config.TextColumn(disabled=True),
        "site_nome": st.column_config.TextColumn(disabled=True),
        "data_validacao": st.column_config.TextColumn(disabled=True),
        "observacao": st.column_config.TextColumn(width="medium"),
        "validador": st.column_config.TextColumn(width="small"),
    },
    disabled=["status","data","site_nome","data_validacao"],
    key="editor_agnd_v1",
)

if "temp_edits" not in st.session_state or not edited.equals(st.session_state["temp_edits"]):
    st.session_state["temp_edits"] = edited.copy()

col_save1, col_save2 = st.columns([1,6])
with col_save1:
    save_clicked = st.button("💾 Salvar alterações", type="primary")
with col_save2:
    if st.session_state.get("temp_edits") is not None:
        st.caption("Há edições não salvas. Clique em **Salvar alterações** para aplicar e publicar.")

def _exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    cols = ["site_nome", "data", "status", "observacao", "validador", "data_validacao"]
    cols = [c for c in cols if c in df.columns]
    out = df[cols].copy()
    out["data"] = pd.to_datetime(out["data"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    dv = pd.to_datetime(out["data_validacao"], errors="coerce")
    out["data_validacao"] = dv.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    for c in set(out.columns) - {"data", "data_validacao"}:
        out[c] = out[c].fillna("").astype(str)

    buf = io.BytesIO()
    # usa openpyxl para evitar dependência de xlsxwriter
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        out.to_excel(writer, index=False, sheet_name="validacao")
    buf.seek(0)
    return buf.read()

if save_clicked:
    base = st.session_state.df_validado.copy()
    e = st.session_state.temp_edits.copy()
    e["data"] = pd.to_datetime(e["data"]).dt.date

    def decide(row):
        if bool(row.get("nao", False)): return "Rejeitada"
        if bool(row.get("sim", False)): return "Aprovada"
        return "Pendente"

    e["status_novo"] = e.apply(decide, axis=1)
    keys = ["site_nome", "data"]
    upd_cols = ["status_novo", "observacao", "validador"]

    merged = base.drop(columns=["observacao","validador"], errors="ignore").merge(
        e[keys + upd_cols], on=keys, how="left"
    )
    mask_new = ~merged["status_novo"].isna()
    merged.loc[mask_new, "status"] = merged.loc[mask_new, "status_novo"]
    merged = merged.drop(columns=["status_novo"])

    # coloca data de validação quando muda para Aprovada/Rejeitada e não tinha timestamp
    mudou = merged["status"].isin(["Aprovada","Rejeitada"]) & merged["data_validacao"].isna()
    ts_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)  # timestamp em UTC (naive)
    merged.loc[mudou, "data_validacao"] = ts_now

    st.session_state.df_validado = merged
    st.session_state.temp_edits = None
    st.success("Alterações salvas localmente.")

    # publica no GitHub
    try:
        xlsb = _exportar_excel_bytes(st.session_state.df_validado)
        meta = gh_save_snapshot(xlsb, author=st.session_state.get("usuario_logado",""))
        st.session_state.ultimo_meta = meta
        st.info(f"Publicado no GitHub: `{meta['path']}` (UTC: {meta['saved_at_utc']})")
    except Exception as e:
        st.warning(f"Salvou localmente, mas falhou ao publicar no GitHub: {e}")

# -----------------------------------------------------------------------------
# CALENDÁRIO (mês selecionado)
# -----------------------------------------------------------------------------
def montar_calendario(df_mes: pd.DataFrame, mes_ano: str,
                      only_color_with_events: bool = True,
                      show_badges: bool = True) -> go.Figure:
    primeiro = pd.to_datetime(f"{mes_ano}-01")
    ultimo = (pr
imeiro + pd.offsets.MonthEnd(1))
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
        # domingo como coluna 0
        return (d.weekday() + 1) % 7

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
            fig.add_shape(
                type="rect", x0=c, x1=c+1, y0=5-r, y1=6-r,
                line=dict(width=1, color="#90A4AE"),
                fillcolor=fill
            )
            fig.add_annotation(
                x=c+0.05, y=5-r+0.85, text=str(d.day),
                showarrow=False, xanchor="left", yanchor="top", font=dict(size=12)
            )

            inf = info_map.get(d.date())
            if show_badges and (inf is not None):
                y0 = 5-r+0.18
                badges = []
                if inf["aprovadas"] > 0: badges.append(("●", "#2e7d32"))
                if inf["rejeitadas"] > 0: badges.append(("●", "#c62828"))
                if inf["pendentes"] > 0: badges.append(("●", "#607D8B"))
                x0 = c+0.08
                for ch, colr in badges:
                    fig.add_annotation(
                        x=x0, y=y0, text=f"<span style='color:{colr}'>{ch}</span>",
                        showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=12)
                    )
                    x0 += 0.12
                txt_cnt = f"{inf['aprovadas']}A/{inf['rejeitadas']}R/{inf['pendentes']}P"
                fig.add_annotation(
                    x=c+0.95, y=5-r+0.18, text=txt_cnt,
                    showarrow=False, xanchor="right", yanchor="bottom", font=dict(size=10)
                )

            # ponto invisível apenas para hover detalhado
            if inf is not None:
                sites_txt = ", ".join(inf["sites"]) if inf["sites"] else "-"
                hover = (f"{d.strftime('%Y-%m-%d')}<br>"
                         f"Aprovadas: {inf['aprovadas']} | Rejeitadas: {inf['rejeitadas']} | Pendentes: {inf['pendentes']}<br>"
                         f"Sites: {sites_txt}")
                fig.add_trace(go.Scatter(
                    x=[c+0.5], y=[5-r+0.5], mode="markers",
                    marker=dict(size=1, color="rgba(0,0,0,0)"),
                    hovertemplate=hover, showlegend=False
                ))

    fig.update_xaxes(visible=False); fig.update_yaxes(visible=False)
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="white", plot_bgcolor="white"))
    return fig

st.subheader(f"📆 Ações em lote por dia — {label_mes}")
dias_disponiveis = sorted(pd.to_datetime(fdf["data"]).dt.date.unique())
if dias_disponiveis:
    d_sel = st.selectbox("Dia", options=dias_disponiveis,
                         format_func=lambda d: d.strftime("%Y-%m-%d"))
    cA, cB, _ = st.columns([1,1,6])
    with cA:
        if st.button("✅ Aprovar tudo do dia"):
            base = st.session_state.df_validado
            idx = (pd.to_datetime(base["data"]).dt.date == d_sel) & base["site_nome"].isin(sel_sites) & (base["yyyymm"] == mes_ano)
            base.loc[idx, "status"] = "Aprovada"
            ts_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
            base.loc[idx & base["data_validacao"].isna(), "data_validacao"] = ts_now
            st.session_state.df_validado = base
            st.success(f"Aprovado tudo em {d_sel}.")
            try:
                xlsb = _exportar_excel_bytes(st.session_state.df_validado)
                meta = gh_save_snapshot(xlsb, author=st.session_state.get("usuario_logado",""))
                st.session_state.ultimo_meta = meta
                st.info(f"Publicado no GitHub: `{meta['path']}`")
            except Exception as e:
                st.warning(f"Falhou ao publicar no GitHub: {e}")
    with cB:
        if st.button("⛔ Rejeitar tudo do dia"):
            base = st.session_state.df_validado
            idx = (pd.to_datetime(base["data"]).dt.date == d_sel) & base["site_nome"].isin(sel_sites) & (base["yyyymm"] == mes_ano)
            base.loc[idx, "status"] = "Rejeitada"
            ts_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
            base.loc[idx & base["data_validacao"].isna(), "data_validacao"] = ts_now
            st.session_state.df_validado = base
            st.success(f"Rejeitado tudo em {d_sel}.")
            try:
                xlsb = _exportar_excel_bytes(st.session_state.df_validado)
                meta = gh_save_snapshot(xlsb, author=st.session_state.get("usuario_logado",""))
                st.session_state.ultimo_meta = meta
                st.info(f"Publicado no GitHub: `{meta['path']}`")
            except Exception as e:
                st.warning(f"Falhou ao publicar no GitHub: {e}")
else:
    st.caption("Sem passagens no mês/site(s) filtrados.")

# CALENDÁRIO
st.subheader(f"Calendário do mês selecionado — {label_mes}")
fig = montar_calendario(
    fdf,
    mes_ano,
    only_color_with_events=True,
    show_badges=True
)
st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

# Exportar manual (download)
st.markdown("---")
st.subheader("Exportar arquivo validado")
colA, colB = st.columns([1,2])
with colA:
    nome_arquivo = st.text_input("Nome do arquivo", value="passagens_validado.xlsx")
with colB:
    xlsb = _exportar_excel_bytes(st.session_state.df_validado)
    st.download_button(
        "Baixar Excel validado",
        data=xlsb,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# Diagnóstico (opcional)
with st.expander("🔧 Diagnóstico GitHub"):
    has_token  = "github_token"  in st.secrets
    has_repo   = "github_repo"   in st.secrets
    has_branch = "github_branch" in st.secrets
    has_root   = "gh_data_root"  in st.secrets
    st.write("Secrets:", {
        "github_token": has_token, "github_repo": has_repo,
        "github_branch": has_branch, "gh_data_root": has_root
    })
    if has_repo:   st.write("Repo:", st.secrets["github_repo"])
    if has_branch: st.write("Branch:", st.secrets["github_branch"])
    if has_root:   st.write("Raiz:", st.secrets["gh_data_root"])
    if st.button("🔄 Recarregar último snapshot do GitHub"):
        st.session_state.df_validado = load_latest_snapshot_df()
        st.session_state.ultimo_meta = load_latest_meta()
        st.experimental_rerun()

