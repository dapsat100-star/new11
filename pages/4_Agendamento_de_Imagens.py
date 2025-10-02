# -*- coding: utf-8 -*-
# pages/4_Agendamento_de_Imagens.py
# Módulo Agendamento de Imagens (cronograma)
# - Sem UI de upload: carrega direto do GitHub
# - Se houver secrets agenda_source_path (ou AGENDA_SOURCE_PATH), usa esse arquivo fixo.
# - Senão, carrega o último snapshot em gh_data_root.
# - Salva snapshots em cronograma/data/validado/YYYY/MM/validado-*.xlsx
# - Sidebar sempre fixa, com Logout e links para os módulos.

import io, os, base64, json, datetime as dt
from typing import Dict, List, Optional
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ==== Auth (logout + guard) ====
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# ----------------- Página -----------------
st.set_page_config(
    page_title="Agendamento de Imagens",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# === CSS: sidebar sempre aberta + sem botão de colapsar ===
st.markdown("""
<style>
header[data-testid="stHeader"]{ display:none !important; }
section[data-testid="stSidebar"], aside[data-testid="stSidebar"]{
  display:block !important; visibility:visible !important; transform:none !important;
}
div[data-testid="collapsedControl"]{ display:none !important; }
div[data-testid="stSidebarNav"]{ display:none !important; }
section[data-testid="stSidebar"] nav,
section[data-testid="stSidebar"] [role="navigation"]{ display:none !important; }
@media (max-width:3000px){
  section[data-testid="stSidebar"]{ min-width:300px !important; width:300px !important; }
}
main.block-container{ padding-top:0.0rem !important; }
</style>
""", unsafe_allow_html=True)

# ---- Guard de sessão ----
auth_ok   = st.session_state.get("authentication_status", None)
user_name = st.session_state.get("name") or st.session_state.get("username")
if not auth_ok:
    st.warning("Sessão expirada ou não autenticada.")
    st.markdown('<a href="/" target="_self">🔒 Voltar à página de login</a>', unsafe_allow_html=True)
    st.stop()

# ============== Sidebar (logout + atalhos) ==============
def _build_authenticator():
    try:
        with open("auth_config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.load(f, Loader=SafeLoader)
        return stauth.Authenticate(
            cfg["credentials"], cfg["cookie"]["name"], cfg["cookie"]["key"], cfg["cookie"]["expiry_days"]
        )
    except Exception:
        return None

with st.sidebar:
    st.success(f"Logado como: {user_name or 'usuário'}")
    _auth = _build_authenticator()
    if _auth:
        try:
            _auth.logout(location="sidebar")
        except Exception:
            _auth.logout("Sair", "sidebar")
    st.markdown("---")
    # Atalhos para módulos
    def _first_existing(*cands):
        for p in cands:
            if Path(p).exists():
                return p
        return cands[0]
    st.page_link(_first_existing("pages/1_Estatisticas_Gerais.py","1_Estatisticas_Gerais.py"),
                 label="ESTATÍSTICAS", icon="📊")
    st.page_link(_first_existing("pages/2_Geoportal.py","2_Geoportal.py"),
                 label="GEOPORTAL", icon="🗺️")
    st.page_link(_first_existing("pages/3_Relatorio_OGMP_2_0.py","3_Relatorio_OGMP_2_0.py"),
                 label="RELATÓRIO", icon="📄")
    st.page_link(_first_existing("pages/4_Agendamento_de_Imagens.py","4_Agendamento_de_Imagens.py"),
                 label="AGENDAMENTO DE IMAGENS", icon="🗓️")
    st.markdown("---")

# ========================== Config GitHub ==========================
def _get_conf(key: str, env: str, default=None):
    try:
        val = st.secrets.get(key)
    except Exception:
        val = None
    if val in (None, ""):
        val = os.getenv(env, default)
    return val

# Preferência: valores com prefixo 'agenda_' (se quiser separar deste módulo)
def _agenda(key: str, env: str, default=None):
    v = _get_conf(f"agenda_{key}", f"AGENDA_{env}", None)
    return v if v not in (None, "") else _get_conf(f"github_{key}", f"GITHUB_{env}", default)

def _gh_token():  return _agenda("token",  "TOKEN")
def _gh_repo():   return _agenda("repo",   "REPO")
def _gh_branch(): return _agenda("branch", "BRANCH", "main")
def _gh_root():   return _agenda("root",   "ROOT", "data/validado")
def _gh_src():    return _agenda("source_path", "SOURCE_PATH")  # caminho fixo opcional, ex.: entrada/cronograma.xlsx

def _gh_headers():
    token = _gh_token()
    if not token:
        raise RuntimeError("Faltando token do GitHub (agenda_token/GITHUB_TOKEN).")
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

# ===== Helpers GitHub (listar e baixar) =====
def _list_contents(path: str):
    url = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}?ref={_gh_branch()}"
    headers = _gh_headers() if _gh_token() else {}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()

def _list_all_xlsx(path: str):
    items = _list_contents(path)
    files = []
    for it in items:
        if it["type"] == "file" and it["name"].lower().endswith(".xlsx"):
            files.append(it["path"])
        elif it["type"] == "dir":
            files.extend(_list_all_xlsx(it["path"]))
    return files

def fetch_file_bytes(rel_path: str) -> bytes:
    """Lê um arquivo do repo (API c/token se privado, RAW se público)."""
    if _gh_token():
        api = f"https://api.github.com/repos/{_gh_repo()}/contents/{rel_path}?ref={_gh_branch()}"
        r = requests.get(api, headers=_gh_headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        return base64.b64decode(data["content"])
    else:
        raw = f"https://raw.githubusercontent.com/{_gh_repo()}/{_gh_branch()}/{rel_path}"
        r = requests.get(raw, timeout=30); r.raise_for_status()
        return r.content

# ===== Snapshots (salvar) =====
def gh_get_file_sha(path: str):
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
    now = dt.datetime.utcnow()
    yyyy = now.strftime("%Y"); mm = now.strftime("%m"); stamp = now.strftime("%Y%m%d-%H%M%S")
    excel_rel_path = f"{root}/{yyyy}/{mm}/validado-{stamp}.xlsx"
    gh_put_file(excel_rel_path, xls_bytes, f"[streamlit] snapshot {stamp} (autor={author or 'anon'})", None)
    latest = {"saved_at_utc": now.isoformat()+"Z", "author": author or "", "path": excel_rel_path}
    latest_path = f"{root}/latest.json"
    sha_old = gh_get_file_sha(latest_path)
    gh_put_file(latest_path, json.dumps(latest, ensure_ascii=False, indent=2).encode("utf-8"),
                f"[streamlit] update latest -> {excel_rel_path}", sha_old)
    return latest

# ===== Auto-load (último snapshot ou arquivo fixo) =====
def load_latest_meta() -> dict | None:
    try:
        root = _gh_root().rstrip("/")
        url = f"https://raw.githubusercontent.com/{_gh_repo()}/{_gh_branch()}/{root}/latest.json"
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def load_latest_snapshot_df() -> Optional[pd.DataFrame]:
    try:
        all_files = _list_all_xlsx(_gh_root())
        if not all_files: return None
        all_files.sort(reverse=True)
        latest = all_files[0]
        content = fetch_file_bytes(latest)
        df = pd.read_excel(io.BytesIO(content))
        keep = ["site_nome","data","status","observacao","validador","data_validacao"]
        df = df[[c for c in keep if c in df.columns]].copy()
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
        df["data_validacao"] = pd.to_datetime(df.get("data_validacao", pd.NaT), errors="coerce")
        df["observacao"] = df.get("observacao","").astype(str)
        df["validador"]  = df.get("validador","").astype(str)
        df["status"]     = df.get("status","Pendente").astype(str)
        df["yyyymm"]     = pd.to_datetime(df["data"]).dt.strftime("%Y-%m")
        return df.sort_values(["data","site_nome"]).reset_index(drop=True)
    except Exception as e:
        st.warning(f"Não consegui carregar o último snapshot do GitHub: {e}")
        return None

# ===== Normalização para planilha “matriz mês/ano” =====
PT_MESES: Dict[str, int] = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

def detectar_colunas_mes(df: pd.DataFrame) -> List[str]:
    cols_mes = []
    for c in df.columns:
        s = str(c).strip().replace("\xa0", " ").lower()
        partes = s.split()
        if len(partes) == 2 and partes[0] in PT_MESES:
            try:
                _ = int(partes[1]); cols_mes.append(c)
            except Exception:
                pass
    return cols_mes

def normalizar_planilha_matriz(df_raw: pd.DataFrame, col_site: Optional[str] = None) -> pd.DataFrame:
    df = df_raw.copy()
    df.columns = [str(c).strip().replace("\xa0", " ") for c in df.columns]
    if col_site is None:
        col_site = df.columns[0]
    if col_site != "site_nome":
        df = df.rename(columns={col_site: "site_nome"})
    cols_mes = detectar_colunas_mes(df)
    if not cols_mes:
        raise ValueError("Não foram encontradas colunas no formato 'Mês Ano' (ex.: 'Outubro 2025').")
    registros = []
    for _, row in df.iterrows():
        site = row["site_nome"]
        for cm in cols_mes:
            dias_str = row[cm]
            if pd.isna(dias_str) or str(dias_str).strip() == "":
                continue
            mes_nome, ano_str = str(cm).strip().split()
            mes_num = PT_MESES.get(mes_nome.lower()); ano = int(ano_str)
            dias = [d.strip() for d in str(dias_str).split(",") if d.strip() != ""]
            for d in dias:
                try:
                    di = int(d)
                    dt_ = pd.Timestamp(year=ano, month=mes_num, day=di)
                    registros.append({
                        "site_nome": site, "data": dt_.date(), "status": "Pendente",
                        "observacao": "", "validador": "", "data_validacao": pd.NaT
                    })
                except Exception:
                    continue
    df_expl = pd.DataFrame(registros)
    if df_expl.empty:
        raise ValueError("Nenhuma data válida foi encontrada (ex.: células '10,12,13').")
    df_expl["yyyymm"] = pd.to_datetime(df_expl["data"]).dt.strftime("%Y-%m")
    return df_expl.sort_values(["data", "site_nome"]).reset_index(drop=True)

# ===== Escrita Excel (openpyxl) =====
def write_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="validacao")
    buf.seek(0)
    return buf.read()

def exportar_excel(df: pd.DataFrame) -> bytes:
    cols = ["site_nome", "data", "status", "observacao", "validador", "data_validacao"]
    cols = [c for c in cols if c in df.columns]
    df_exp = df[cols].copy()
    df_exp["data"] = pd.to_datetime(df_exp["data"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    dv = pd.to_datetime(df_exp["data_validacao"], errors="coerce")
    df_exp["data_validacao"] = dv.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    for c in set(df_exp.columns) - {"data", "data_validacao"}:
        df_exp[c] = df_exp[c].fillna("").astype(str)
    return write_excel_bytes(df_exp)

def exportar_excel_full(df: pd.DataFrame) -> bytes:
    return exportar_excel(df)

# ===== Carregamento automático (sem uploader) =====
st.title("🛰️ Calendário de Validação (GitHub)")
st.caption("Planilha carregada automaticamente do repositório de dados. Marque **sim/nao** e clique **Salvar** para gerar um snapshot no GitHub.")

# Estado
if "df_validado" not in st.session_state:
    st.session_state.df_validado = None
if "temp_edits" not in st.session_state:
    st.session_state.temp_edits = None

def _load_from_repo() -> Optional[pd.DataFrame]:
    src = _gh_src()
    try:
        if src:  # caminho fixo
            content = fetch_file_bytes(src)
            df_raw = pd.read_excel(io.BytesIO(content))
            # já no formato final?
            cols_low = {c.lower() for c in df_raw.columns}
            if {"site_nome","data"}.issubset(cols_low):
                df = df_raw.copy()
                df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
                df["data_validacao"] = pd.to_datetime(df.get("data_validacao", pd.NaT), errors="coerce")
                df["observacao"] = df.get("observacao","").astype(str)
                df["validador"]  = df.get("validador","").astype(str)
                df["status"]     = df.get("status","Pendente").astype(str)
                df["yyyymm"]     = pd.to_datetime(df["data"]).dt.strftime("%Y-%m")
                st.session_state["__fonte_path"] = src
                return df.sort_values(["data","site_nome"]).reset_index(drop=True)
            # senão, é matriz “Mês Ano”
            df_norm = normalizar_planilha_matriz(df_raw, None)
            st.session_state["__fonte_path"] = src
            return df_norm
        # Sem caminho fixo → usa último snapshot
        meta = load_latest_meta()
        df_auto = load_latest_snapshot_df()
        if meta and "path" in meta:
            st.session_state["__fonte_path"] = meta["path"]
        else:
            st.session_state["__fonte_path"] = f"{_gh_root()}/*(último)*"
        return df_auto
    except Exception as e:
        st.error(f"Falha ao carregar planilha do GitHub: {e}")
        return None

if st.session_state.df_validado is None:
    with st.spinner("Carregando planilha do GitHub..."):
        st.session_state.df_validado = _load_from_repo()
    if st.session_state.df_validado is not None:
        st.success("✅ Planilha carregada do GitHub.")
    else:
        st.stop()

# Info da fonte + recarregar
fonte = st.session_state.get("__fonte_path","(desconhecido)")
colI, colR = st.columns([6,1])
with colI:
    st.info(f"**Fonte:** `{_gh_repo()} / {_gh_branch()} / {fonte}`")
with colR:
    if st.button("↻ Recarregar"):
        st.session_state.df_validado = None
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

# ===== Filtros =====
with st.sidebar:
    st.header("Filtros")
    dfv = st.session_state.df_validado
    sites = sorted(dfv["site_nome"].unique())
    site_sel = st.multiselect("Sites", options=sites, default=sites)
    meses = sorted(dfv["yyyymm"].unique())
    mes_ano = st.selectbox("Mês", options=meses, index=max(0, len(meses)-1), key="mes_ano")
    st.checkbox("Colorir só dias com passagem", value=True, key="only_color_with_events")
    st.checkbox("Mostrar bolinhas/contagem", value=True, key="show_badges")
    st.text_input("Seu nome (autor do commit)", key="usuario_logado", placeholder="ex.: Márcio")

autor_atual = st.session_state.get("usuario_logado", "").strip() or "—"
st.caption(f"👤 Autor atual para commits: **{autor_atual}**")

mask = st.session_state.df_validado["site_nome"].isin(site_sel) & (st.session_state.df_validado["yyyymm"] == st.session_state.get("mes_ano", mes_ano))
fdf = (st.session_state.df_validado.loc[mask]
       .copy().sort_values(["data", "site_nome"])
       if not st.session_state.df_validado.empty else st.session_state.df_validado.copy())

# ===== Editor =====
st.subheader("Tabela de passagens para validar")
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
        "nao": st.column_config.CheckboxColumn(label="Rejeitar (nao)", help="Marca como Rejeitada"),
        "status": st.column_config.TextColumn(disabled=True),
        "data": st.column_config.TextColumn(disabled=True),
        "site_nome": st.column_config.TextColumn(disabled=True),
        "data_validacao": st.column_config.TextColumn(disabled=True),
        "observacao": st.column_config.TextColumn(width="medium"),
        "validador": st.column_config.TextColumn(width="small"),
    },
    disabled=["status", "data", "site_nome", "data_validacao"],
    key="editor_v3",
)

col_save1, col_save2 = st.columns([1,6])
with col_save1:
    save_clicked = st.button("💾 Salvar alterações", type="primary")
with col_save2:
    if st.session_state.temp_edits is not None:
        st.caption("Há edições não salvas. Clique em **Salvar alterações** para aplicar.")

if st.session_state.temp_edits is None or not edited.equals(st.session_state.temp_edits):
    st.session_state.temp_edits = edited.copy()

if save_clicked:
    base = st.session_state.df_validado
    e = st.session_state.temp_edits.copy()
    e["data"] = pd.to_datetime(e["data"]).dt.date

    def decide(row):
        if row.get("nao", False): return "Rejeitada"
        if row.get("sim", False): return "Aprovada"
        return "Pendente"

    e["status_novo"] = e.apply(decide, axis=1)
    keys = ["site_nome", "data"]
    upd_cols = ["status_novo", "observacao", "validador"]
    merged = base.drop(columns=["observacao", "validador"], errors="ignore").merge(e[keys + upd_cols], on=keys, how="left")
    mask_new = ~merged["status_novo"].isna()
    merged.loc[mask_new, "status"] = merged.loc[mask_new, "status_novo"]
    merged = merged.drop(columns=["status_novo"])
    mudou = merged["status"].isin(["Aprovada", "Rejeitada"]) & merged["data_validacao"].isna()
    merged.loc[mudou, "data_validacao"] = pd.Timestamp.now(tz="UTC").tz_convert(None)
    st.session_state.df_validado = merged
    st.session_state.temp_edits = None
    st.success("Alterações salvas!")
    # publicar no GitHub
    try:
        xlsb = exportar_excel(st.session_state.df_validado)
        usuario = st.session_state.get("usuario_logado", "")
        meta = gh_save_snapshot(xlsb, author=usuario)
        st.info(f"Salvo no GitHub: `{meta['path']}` (UTC: {meta['saved_at_utc']})")
    except Exception as e:
        st.warning(f"Salvou localmente, mas falhou ao publicar no GitHub: {e}")
    # recalc
    mask = st.session_state.df_validado["site_nome"].isin(site_sel) & (st.session_state.df_validado["yyyymm"] == st.session_state.get("mes_ano", mes_ano))
    fdf = (st.session_state.df_validado.loc[mask]
           .copy().sort_values(["data", "site_nome"])
           if not st.session_state.df_validado.empty else st.session_state.df_validado.copy())

# ===== Ações em lote =====
st.markdown("### ⚙️ Ações em lote por dia")
dias_disponiveis = sorted(pd.to_datetime(fdf["data"]).dt.date.unique())
if dias_disponiveis:
    d_sel = st.selectbox("Dia", options=dias_disponiveis, format_func=lambda d: d.strftime("%Y-%m-%d"))
    cA, cB, _ = st.columns([1,1,6])
    with cA:
        if st.button("✅ Aprovar tudo do dia"):
            base = st.session_state.df_validado
            idx = (pd.to_datetime(base["data"]).dt.date == d_sel) & base["site_nome"].isin(site_sel) & (base["yyyymm"] == st.session_state.get("mes_ano", mes_ano))
            base.loc[idx, "status"] = "Aprovada"
            base.loc[idx & base["data_validacao"].isna(), "data_validacao"] = pd.Timestamp.now(tz="UTC").tz_convert(None)
            st.session_state.df_validado = base
            st.success(f"Aprovado tudo em {d_sel}.")
            try:
                xlsb = exportar_excel(st.session_state.df_validado)
                usuario = st.session_state.get("usuario_logado", "")
                meta = gh_save_snapshot(xlsb, author=usuario)
                st.info(f"Salvo no GitHub: `{meta['path']}` (UTC: {meta['saved_at_utc']})")
            except Exception as e:
                st.warning(f"Falhou ao publicar no GitHub: {e}")
    with cB:
        if st.button("⛔ Rejeitar tudo do dia"):
            base = st.session_state.df_validado
            idx = (pd.to_datetime(base["data"]).dt.date == d_sel) & base["site_nome"].isin(site_sel) & (base["yyyymm"] == st.session_state.get("mes_ano", mes_ano))
            base.loc[idx, "status"] = "Rejeitada"
            base.loc[idx & base["data_validacao"].isna(), "data_validacao"] = pd.Timestamp.now(tz="UTC").tz_convert(None)
            st.session_state.df_validado = base
            st.success(f"Rejeitado tudo em {d_sel}.")
            try:
                xlsb = exportar_excel(st.session_state.df_validado)
                usuario = st.session_state.get("usuario_logado", "")
                meta = gh_save_snapshot(xlsb, author=usuario)
                st.info(f"Salvo no GitHub: `{meta['path']}` (UTC: {meta['saved_at_utc']})")
            except Exception as e:
                st.warning(f"Falhou ao publicar no GitHub: {e}")
else:
    st.caption("Sem passagens no mês/site(s) filtrados.")

# ===== Calendário =====
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

    def weekday_dom(d: pd.Timestamp) -> int: return (d.weekday() + 1) % 7
    grid = np.full((6, 7), None, dtype=object); week = 0
    for d in dias:
        col = weekday_dom(d)
        if col == 0 and d.day != 1: week += 1
        grid[week, col] = d

    fig = go.Figure()
    for r in range(6):
        for c in range(7):
            d = grid[r, c]
            if d is None: continue
            fill = cor_do_dia(d)
            fig.add_shape(type="rect", x0=c, x1=c+1, y0=5-r, y1=6-r, line=dict(width=1, color="#90A4AE"), fillcolor=fill)
            fig.add_annotation(x=c+0.05, y=5-r+0.85, text=str(d.day), showarrow=False, xanchor="left", yanchor="top", font=dict(size=12))
            inf = info_map.get(d.date())
            if show_badges and (inf is not None):
                y0 = 5-r+0.18; badges = []
                if inf["aprovadas"] > 0: badges.append(("●", "#2e7d32"))
                if inf["rejeitadas"] > 0: badges.append(("●", "#c62828"))
                if inf["pendentes"] > 0: badges.append(("●", "#607D8B"))
                x0 = c+0.08
                for ch, colr in badges:
                    fig.add_annotation(x=x0, y=y0, text=f"<span style='color:{colr}'>{ch}</span>", showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=12)); x0 += 0.12
                txt_cnt = f"{inf['aprovadas']}A/{inf['rejeitadas']}R/{inf['pendentes']}P"
                fig.add_annotation(x=c+0.95, y=5-r+0.18, text=txt_cnt, showarrow=False, xanchor="right", yanchor="bottom", font=dict(size=10))
            if inf is not None:
                sites_txt = ", ".join(inf["sites"]) if inf["sites"] else "-"
                hover = (f"{d.strftime('%Y-%m-%d')}<br>"
                         f"Aprovadas: {inf['aprovadas']} | Rejeitadas: {inf['rejeitadas']} | Pendentes: {inf['pendentes']}<br>"
                         f"Sites: {sites_txt}")
                fig.add_trace(go.Scatter(x=[c+0.5], y=[5-r+0.5], mode="markers", marker=dict(size=1, color="rgba(0,0,0,0)"), hovertemplate=hover, showlegend=False))
    fig.update_xaxes(visible=False); fig.update_yaxes(visible=False)
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="white", plot_bgcolor="white")
    return fig

st.subheader("Calendário do mês selecionado")
mes_ano_cur = st.session_state.get("mes_ano") or st.session_state.df_validado["yyyymm"].max()
fig = montar_calendario(
    st.session_state.df_validado[st.session_state.df_validado["yyyymm"] == mes_ano_cur],
    mes_ano_cur,
    only_color_with_events=st.session_state.get("only_color_with_events", True),
    show_badges=st.session_state.get("show_badges", True),
)
st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

# ===== Exportar =====
st.markdown("---"); st.subheader("Exportar")
nome_arquivo = st.text_input("Nome do arquivo", value="passagens_validado.xlsx")
xlsb = exportar_excel_full(st.session_state.df_validado)
st.download_button("Baixar Excel validado", data=xlsb, file_name=nome_arquivo,
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ===== Diagnóstico GitHub =====
with st.expander("🔧 Diagnóstico GitHub", expanded=False):
    has_token  = bool(_gh_token())
    has_repo   = bool(_gh_repo())
    has_branch = bool(_gh_branch())
    has_root   = bool(_gh_root())
    st.write("Secrets:", {"github_token": has_token, "github_repo": has_repo,
                          "github_branch": has_branch, "gh_data_root": has_root})
    if has_repo:   st.write("Repo:", _gh_repo())
    if has_branch: st.write("Branch:", _gh_branch())
    if has_root:   st.write("Raiz:", _gh_root())
    disabled = not (has_token and has_repo)
    if st.button("🔎 Testar conexão e gravar ping.txt", disabled=disabled):
        try:
            now = dt.datetime.utcnow(); stamp = now.strftime("%Y%m%d-%H%M%S")
            path = f"{_gh_root()}/diagnostics/ping-{stamp}.txt"
            payload = {"message": f"diagnostics: ping {stamp}",
                       "content": base64.b64encode(f'ping {stamp}\n'.encode("utf-8")).decode("utf-8"),
                       "branch": _gh_branch()}
            url  = f"https://api.github.com/repos/{_gh_repo()}/contents/{path}"
            r = requests.put(url, headers=_gh_headers(), json=payload, timeout=30)
            st.write("HTTP:", r.status_code)
            try: st.json(r.json())
            except Exception: st.write(r.text)
            if r.status_code in (200, 201):
                st.success("✅ Consegui gravar no GitHub. O fluxo de salvar Excel deve funcionar também.")
            else:
                st.error("❌ Não consegui gravar. Veja o JSON acima (repo/branch/token).")
        except Exception as e:
            st.exception(e)
