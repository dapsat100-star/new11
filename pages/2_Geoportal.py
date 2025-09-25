# -*- coding: utf-8 -*-
# pages/2_Geoportal.py
# Geoportal — 1 único gráfico: linha (spline opcional) + barras de incerteza

import io
import base64
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ==== Auth (apenas para botão Sair e guard) ====
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# ===================== CONFIG =====================
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/dapsat100-star/geoportal/main"
LOGO_REL_PATH    = "images/logomavipe.jpeg"  # usado no PDF
# ==================================================

# Mapa (opcional)
try:
    import folium
    from streamlit_folium import st_folium
    HAVE_MAP = True
except Exception:
    HAVE_MAP = False

# PDF deps
from datetime import datetime, timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from urllib.request import urlopen

# Fallback de renderização do gráfico para o PDF (Matplotlib)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ----------------- Página -----------------
st.set_page_config(page_title="Geoportal — Metano", layout="wide", initial_sidebar_state="expanded")

# === CSS para UI (remove menu multipágina e reduz padding do topo) ===
st.markdown(
    """
<style>
header[data-testid="stHeader"] { display: none !important; }
section[data-testid="stSidebar"], aside[data-testid="stSidebar"] {
  display: block !important; transform: none !important; visibility: visible !important;
}
div[data-testid="collapsedControl"]{ display:block !important; }
div[data-testid="stSidebarNav"] { display: none !important; }
section[data-testid="stSidebar"] nav { display: none !important; }
section[data-testid="stSidebar"] [role="navigation"] { display: none !important; }
#top-right-logo { position: fixed; top: 12px; right: 16px; z-index: 1000; }
main.block-container { padding-top: 0.0rem !important; }
</style>
""",
    unsafe_allow_html=True,
)

# === Logo no canto superior direito ===
logo_ui_path = Path(__file__).parent / "logomavipe.jpeg"
if logo_ui_path.exists():
    b64_logo = base64.b64encode(logo_ui_path.read_bytes()).decode("ascii")
    st.markdown(
        f"<div id='top-right-logo'><img src='data:image/jpeg;base64,{b64_logo}' width='120'/></div>",
        unsafe_allow_html=True,
    )

st.title("📷 Geoportal de Metano — gráfico único")

# ---- Guard de sessão ----
auth_ok   = st.session_state.get("authentication_status", None)
user_name = st.session_state.get("name") or st.session_state.get("username")
if not auth_ok:
    st.warning("Sessão expirada ou não autenticada.")
    st.markdown('<a href="/" target="_self">🔒 Voltar à página de login</a>', unsafe_allow_html=True)
    st.stop()

# ================= Sidebar =================
def _build_authenticator():
    try:
        with open("auth_config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.load(f, Loader=SafeLoader)
        return stauth.Authenticate(
            cfg["credentials"],
            cfg["cookie"]["name"],
            cfg["cookie"]["key"],
            cfg["cookie"]["expiry_days"],
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

    st.header("📁 Carregar o Excel")
    uploaded = st.file_uploader("Upload do Excel (.xlsx)", type=["xlsx"])

    st.markdown("---")
    with st.expander("⚙️ Opções do gráfico"):
        freq = st.selectbox("Frequência (para agregação)", ["Diário","Semanal","Mensal","Trimestral"], index=2)
        agg = st.selectbox("Agregação da série", ["média","mediana","máx","mín"], index=0)
        smooth = st.selectbox("Suavização", ["Nenhuma","Média móvel","Exponencial (EMA)"], index=0)
        window = st.slider("Janela/Span (suavização)", 3, 90, 7, step=1)
        line_spline = st.checkbox("Linha como spline", value=True)
        show_unc_bars = st.checkbox("Mostrar barras de incerteza", value=True)
        show_trend = st.checkbox("Mostrar tendência linear", value=False)

# ================= Helpers =================
@st.cache_data
def read_excel_from_bytes(file_bytes) -> Dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(file_bytes, engine="openpyxl")
    return {sn: pd.read_excel(xls, sheet_name=sn, engine="openpyxl") for sn in xls.sheet_names}

def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    if cols:
        cols[0] = "Parametro"
    normed = []
    for c in cols:
        s = str(c).strip()
        if s.lower() in ("lat","latitude"):
            normed.append("Lat")
        elif s.lower() in ("long","lon","longitude"):
            normed.append("Long")
        else:
            normed.append(s)
    df.columns = normed
    return df

# ----------- rótulos de data PT-BR ------------
def _fmt_pt_month(dt: pd.Timestamp) -> str:
    meses = [
        "janeiro","fevereiro","março","abril","maio","junho",
        "julho","agosto","setembro","outubro","novembro","dezembro"
    ]
    return f"{meses[dt.month-1].capitalize()} de {dt.year}"

def extract_dates_from_first_row(df: pd.DataFrame) -> Tuple[List[str], Dict[str, str], List[pd.Timestamp]]:
    cols = list(df.columns)
    try:
        data_idx = cols.index("Data")
    except ValueError:
        data_idx = 3 if len(cols) > 3 else 0
    date_cols = cols[data_idx:]
    labels, stamps = {}, []
    for c in date_cols:
        v = df.loc[0, c] if 0 in df.index else None
        ts = pd.NaT
        if pd.notna(v) and str(v).strip() != "":
            for dayfirst in (True, False):
                try:
                    parsed = pd.to_datetime(v, dayfirst=dayfirst, errors="raise")
                    ts = pd.Timestamp(year=parsed.year, month=parsed.month, day=1)
                    break
                except Exception:
                    continue
        if pd.isna(ts):
            try:
                parsed = pd.to_datetime(str(c), errors="raise", dayfirst=True)
                ts = pd.Timestamp(year=parsed.year, month=parsed.month, day=1)
            except Exception:
                ts = pd.NaT
        labels[c] = _fmt_pt_month(ts) if pd.notna(ts) else str(c)
        stamps.append(ts)
    return date_cols, labels, stamps

def build_record_for_month(df: pd.DataFrame, date_col: str) -> Dict[str, Optional[str]]:
    dfi = df.copy()
    if dfi.columns[0] != "Parametro":
        dfi.columns = ["Parametro"] + list(dfi.columns[1:]]
    dfi["Parametro"] = dfi["Parametro"].astype(str).str.strip()
    dfi = dfi.set_index("Parametro", drop=True)
    rec = {param: dfi.loc[param, date_col] for param in dfi.index}
    rec["_lat"] = df["Lat"].dropna().iloc[0] if "Lat" in df.columns and df["Lat"].notna().any() else None
    rec["_long"] = df["Long"].dropna().iloc[0] if "Long" in df.columns and df["Long"].notna().any() else None
    return rec

def resolve_image_target(path_str: str) -> Optional[str]:
    if path_str is None or (isinstance(path_str, float) and pd.isna(path_str)): return None
    s = str(path_str).strip()
    if not s: return None
    s = s.replace("\\","/"); s = s[2:] if s.startswith("./") else s
    if s.lower().startswith(("http://","https://")): return s
    return f"{DEFAULT_BASE_URL.rstrip('/')}/{s.lstrip('/')}"

# … (resto das funções auxiliares como extract_series, resample_and_smooth, get_from_dfi — iguais ao que já passamos antes)

# ================= Fluxo principal =================
# (… idem código anterior …)

with right:
    st.subheader("Detalhes do Registro")
    dfi = df_site.copy()
    if dfi.columns[0] != "Parametro":
        dfi.columns = ["Parametro"] + list(dfi.columns[1:]]
    dfi["Parametro"] = dfi["Parametro"].astype(str).str.strip()
    dfi = dfi.set_index("Parametro", drop=True)

    # métricas principais
    k1, k2, k3 = st.columns(3)
    v_taxa  = get_from_dfi(dfi, selected_col, "Taxa Metano")
    v_inc   = get_from_dfi(dfi, selected_col, "Incerteza")
    v_vento = get_from_dfi(dfi, selected_col, "Velocidade do Vento")
    k1.metric("Taxa Metano", f"{v_taxa}" if pd.notna(v_taxa) else "—")
    k2.metric("Incerteza", f"{v_inc}" if pd.notna(v_inc) else "—")
    k3.metric("Vento", f"{v_vento}" if pd.notna(v_vento) else "—")

    st.markdown("---")
    st.caption("Tabela completa (parâmetro → valor):")

    # ---- TABELA com filtros e formatação ----
    table_df = dfi[[selected_col]].copy()
    table_df.columns = ["Valor"]

    # remove "Parametro" e "Imagem"
    drop_keys = {"parametro", "imagem"}
    to_drop = [ix for ix in table_df.index if str(ix).strip().lower() in drop_keys]
    table_df = table_df.drop(index=to_drop, errors="ignore")

    # formata Data de Aquisição sem hora
    import unicodedata
    def _norm(s): 
        return "".join(ch for ch in unicodedata.normalize("NFKD", str(s)) if not unicodedata.category(ch).startswith("M")).strip().lower()

    for ix in table_df.index:
        v = table_df.at[ix, "Valor"]
        if pd.isna(v):
            table_df.at[ix, "Valor"] = ""
            continue
        if _norm(ix) == "data de aquisicao":
            try:
                dt = pd.to_datetime(v, dayfirst=True, errors="raise")
                table_df.at[ix, "Valor"] = dt.strftime("%Y-%m-%d")
            except Exception:
                table_df.at[ix, "Valor"] = str(v).replace(" 00:00:00", "")
        else:
            table_df.at[ix, "Valor"] = str(v)

    st.dataframe(table_df, use_container_width=True)

