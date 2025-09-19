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
# === (Fallback de imagem sem Chrome) Matplotlib/Agg ===
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ==== Auth (apenas para botão Sair e guard) ====
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# ===================== CONFIG =====================
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/dapsat100-star/geoportal/main"
LOGO_REL_PATH    = "images/logomavipe.jpeg"   # usado no PDF
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

# ----------------- Página -----------------
st.set_page_config(page_title="Geoportal — Metano", layout="wide", initial_sidebar_state="expanded")

# === CSS para UI ===
st.markdown(
    """
<style>
header[data-testid="stHeader"] { display: none !important; }
section[data-testid="stSidebar"], aside[data-testid="stSidebar"] {
  display: block !important; transform: none !important; visibility: visible !important;
}
div[data-testid="collapsedControl"]{ display:block !important; }
#top-right-logo { position: fixed; top: 16px; right: 16px; z-index: 1000; }
</style>
""",
    unsafe_allow_html=True,
)

# === Logo no canto superior direito ===
logo_ui_path = Path(__file__).parent / "logomavipe.jpeg"  # arquivo dentro de /pages
if logo_ui_path.exists():
    b64_logo = base64.b64encode(logo_ui_path.read_bytes()).decode("ascii")
    st.markdown(
        f"<div id='top-right-logo'><img src='data:image/jpeg;base64,{b64_logo}' width='120'/></div>",
        unsafe_allow_html=True,
    )

st.title("📷 Geoportal de Metano — gráfico único")

# ---- Link único na sidebar ----
with st.sidebar:
    st.page_link("pages/2_Geoportal.py", label="GEOPORTAL", icon="🗺️")

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
        label, ts = None, pd.NaT
        if pd.notna(v):
            for dayfirst in (True, False):
                try:
                    dt = pd.to_datetime(v, dayfirst=dayfirst, errors="raise")
                    label = dt.strftime("%Y-%m-%d"); ts = pd.to_datetime(label); break
                except Exception:
                    pass
        if not label:
            try:
                dt = pd.to_datetime(str(c), dayfirst=True, errors="raise")
                label = dt.strftime("%Y-%m"); ts = pd.to_datetime(label + "-01", errors="coerce")
            except Exception:
                label = str(c); ts = pd.NaT
        labels[c] = label; stamps.append(ts)
    return date_cols, labels, stamps

def build_record_for_month(df: pd.DataFrame, date_col: str) -> Dict[str, Optional[str]]:
    dfi = df.copy()
    if dfi.columns[0] != "Parametro":
        dfi.columns = ["Parametro"] + list(dfi.columns[1:])   # <- corrigido
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

def extract_series(dfi: pd.DataFrame, date_cols_sorted, dates_ts_sorted, row_name="Taxa Metano"):
    idx_map = {i.lower(): i for i in dfi.index}
    key = idx_map.get(row_name.lower())
    rows = []
    if key is not None:
        for i, col in enumerate(date_cols_sorted):
            val = dfi.loc[key, col] if col in dfi.columns else None
            try:
                num = float(pd.to_numeric(val))
            except Exception:
                num = None
            ts = dates_ts_sorted[i]
            if pd.notna(num) and pd.notna(ts):
                rows.append({"date": ts, "value": float(num)})
    s = pd.DataFrame(rows)
    if not s.empty:
        s = s.sort_values("date").reset_index(drop=True)
    return s

def resample_and_smooth(s: pd.DataFrame, freq_code: str, agg: str, smooth: str, window: int):
    if s.empty: return s
    s2 = s.set_index("date").asfreq("D")
    agg_fn = {"média":"mean","mediana":"median","máx":"max","mín":"min"}[agg]
    out = getattr(s2.resample(freq_code), agg_fn)().dropna().reset_index()
    if smooth == "Média móvel":
        out["value"] = out["value"].rolling(window=window, min_periods=1).mean()
    elif smooth == "Exponencial (EMA)":
        out["value"] = out["value"].ewm(span=window, adjust=False).mean()
    return out

def get_from_dfi(dfi: pd.DataFrame, selected_col: str, name: str, *aliases):
    import unicodedata, re
    def _norm_txt(s)->str:
        if s is None or (isinstance(s,float) and pd.isna(s)): return ""
        s=unicodedata.normalize("NFKD",str(s))
        s="".join(ch for ch in s if not unicodedata.category(ch).startswith("M"))
        return re.sub(r"\\s+"," ",s).strip().lower()
    idx_norm={_norm_txt(ix): ix for ix in dfi.index}
    keys=[_norm_txt(name)] + [_norm_txt(a) for a in aliases]
    for k in keys:
        if k and k in idx_norm:
            return dfi.loc[idx_norm[k], selected_col]
    for nk,orig in idx_norm.items():
        if any(nk.startswith(k) for k in keys if k):
            return dfi.loc[orig, selected_col]
    return None

# =============== Fluxo principal ===============
if uploaded is None:
    st.info("Faça o upload do seu Excel (`.xlsx`) no painel lateral.")
    st.stop()

try:
    book = read_excel_from_bytes(uploaded)
except Exception as e:
    st.error(f"Falha ao ler o Excel enviado. Detalhe: {e}")
    st.stop()

# Normaliza cada aba (site)
book = {name: normalize_cols(df.copy()) for name, df in book.items()}
site_names = sorted(book.keys())

# Escolha do site e data
site = st.selectbox("Selecione o Site", site_names)
df_site = book[site]

# Garante índice numérico para a linha 0 usada pelos rótulos de Data
if df_site.index.name is not None:
    df_site = df_site.reset_index(drop=True)

date_cols, labels, stamps = extract_dates_from_first_row(df_site)
order = sorted(
    range(len(date_cols)),
    key=lambda i: (pd.Timestamp.min if pd.isna(stamps[i]) else stamps[i])
)

date_cols_sorted = [date_cols[i] for i in order]
labels_sorted = [labels[date_cols[i]] for i in order]
stamps_sorted = [stamps[i] for i in order]

selected_label = st.selectbox("Selecione a data", labels_sorted)
selected_col = date_cols_sorted[labels_sorted.index(selected_label)]

# Layout superior: imagem/mapa + tabela/métricas
left, right = st.columns([2,1])

with left:
    rec = build_record_for_month(df_site, selected_col)
    img = resolve_image_target(rec.get("Imagem"))
    st.subheader(f"Imagem — {site} — {selected_label}")
    if img:
        st.image(img, use_container_width=True)
    else:
        st.error("Imagem não encontrada para essa data.")
    if HAVE_MAP and (rec.get("_lat") is not None and rec.get("_long") is not None):
        with st.expander("🗺️ Mostrar mapa (opcional)", expanded=False):
            try:
                m = folium.Map(location=[float(rec["_lat"]), float(rec["_long"])], zoom_start=13, tiles="OpenStreetMap")
                folium.Marker([float(rec["_lat"]), float(rec["_long"])], tooltip=site).add_to(m)
                st_folium(m, height=400, use_container_width=True)
            except Exception as e:
                st.caption(f"[Mapa indisponível: {e}]")

with right:
    st.subheader("Detalhes do Registro")
    dfi = df_site.copy()
    if dfi.columns[0] != "Parametro":
        dfi.columns = ["Parametro"] + list(dfi.columns[1:])   # <- corrigido
    dfi["Parametro"] = dfi["Parametro"].astype(str).str.strip()
    dfi = dfi.set_index("Parametro", drop=True)

    k1, k2, k3 = st.columns(3)
    k1.metric("Taxa Metano", f"{get_from_dfi(dfi, selected_col, 'Taxa Metano')}" if pd.notna(get_from_dfi(dfi, selected_col, 'Taxa Metano')) else "—")
    k2.metric("Incerteza", f"{get_from_dfi(dfi, selected_col, 'Incerteza')}" if pd.notna(get_from_dfi(dfi, selected_col, 'Incerteza')) else "—")
    k3.metric("Vento", f"{get_from_dfi(dfi, selected_col, 'Velocidade do Vento')}" if pd.notna(get_from_dfi(dfi, selected_col, 'Velocidade do Vento')) else "—")

    st.markdown("---")
    st.caption("Tabela completa (parâmetro → valor):")
    table_df = dfi[[selected_col]].copy()
    table_df.columns = ["Valor"]
    if "Imagem" in table_df.index:
        table_df = table_df.drop(index="Imagem")
    table_df = table_df.applymap(lambda v: "" if (pd.isna(v)) else str(v))
    st.dataframe(table_df, use_container_width=True)

# ======== Gráfico único: linha (spline) + barras de incerteza ========
st.markdown("### Série temporal — Taxa de Metano com Incerteza")

# séries cruas por data
series_raw_val = extract_series(dfi, date_cols_sorted, stamps_sorted, row_name="Taxa Metano")
series_raw_unc = extract_series(dfi, date_cols_sorted, stamps_sorted, row_name="Incerteza")

# frequencia e agregação iguais às opções escolhidas
freq_code = {"Diário": "D", "Semanal": "W", "Mensal": "M", "Trimestral": "Q"}[freq]
series_val = resample_and_smooth(series_raw_val, freq_code, agg, smooth, window)
series_unc = resample_and_smooth(series_raw_unc, freq_code, agg, smooth, window)

# alinhar valores e incertezas por data
df_plot = pd.merge(
    series_val.rename(columns={"value": "metano"}),
    series_unc.rename(columns={"value": "incerteza"}),
    on="date", how="left"
).sort_values("date")

if df_plot.empty:
    st.info("Sem dados numéricos suficientes para plotar.")
    fig_line = None  # para PDF
else:
    err_array = df_plot["incerteza"].fillna(0)
    st.session_state["_plot_ctx"] = {
        "x": df_plot["date"].tolist(),
       

