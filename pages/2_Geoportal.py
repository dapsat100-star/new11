# -*- coding: utf-8 -*-
# Geoportal — OGMP 2.0 L5 (com logo no topo-direito, header oculto, menu nativo oculto e link único GEOPORTAL)

import io
import base64
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==== Auth ====
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
st.set_page_config(page_title="Geoportal — Plotly", layout="wide", initial_sidebar_state="expanded")

# === CSS para esconder header do Streamlit e ajustar UI ===
st.markdown("""
<style>
/* Esconde a barra superior (header do Streamlit) */
header[data-testid="stHeader"] {
    display: none !important;
}
#top-right-logo {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 1000;
}
[data-testid="stSidebarNav"]{ display:none !important; }
div[data-testid="collapsedControl"]{ display:block !important; }
</style>
""", unsafe_allow_html=True)

# === Logo Mavipe no canto superior direito ===
logo_ui_path = Path(__file__).parent / "logomavipe.jpeg"  # arquivo está dentro de /pages
if logo_ui_path.exists():
    b64_logo = base64.b64encode(logo_ui_path.read_bytes()).decode("ascii")
    st.markdown(
        f"<div id='top-right-logo'><img src='data:image/jpeg;base64,{b64_logo}' width='120'/></div>",
        unsafe_allow_html=True
    )

st.title("Plataforma Geoespacial DAP Atlas")

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
def force_show_sidebar():
    st.markdown("""
    <style>
      [data-testid='stSidebar']{display:flex !important;}
      div[data-testid="collapsedControl"]{display:block !important;}
    </style>
    """, unsafe_allow_html=True)

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
    force_show_sidebar()
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
    with st.expander("⚙️ Opções de série temporal"):
        freq = st.selectbox("Frequência", ["Diário","Semanal","Mensal","Trimestral"], index=2)
        agg = st.selectbox("Agregação", ["média","mediana","máx","mín"], index=0)
        smooth = st.selectbox("Suavização", ["Nenhuma","Média móvel","Exponencial (EMA)"], index=0)
        window = st.slider("Janela/Span", 3, 90, 7, step=1)
        show_trend = st.checkbox("Mostrar tendência linear", value=False)
        show_conf = st.checkbox("Mostrar banda P10–P90", value=False)
        show_bar = st.checkbox("Mostrar bar plot com barras de erro", value=True)
        err_mode = st.selectbox(
            "Agregação do erro (para o bar plot)",
            ["Média", "RMS", "Máx"],
            index=0,
            help="Como consolidar as incertezas no período agregado das barras."
        )

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
        dfi.columns = ["Parametro"] + list(dfi.columns[1:])
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
            try: num = float(pd.to_numeric(val))
            except Exception: num = None
            ts = dates_ts_sorted[i]
            if pd.notna(num) and pd.notna(ts):
                rows.append({"date": ts, "value": float(num)})
    s = pd.DataFrame(rows)
    if not s.empty: s = s.sort_values("date").reset_index(drop=True)
    return s

# ====== EXTRAÇÃO (valor + erro) ======
def extract_series_pair(dfi: pd.DataFrame,
                        date_cols_sorted, dates_ts_sorted,
                        value_row="Taxa Metano",
                        err_row="Incerteza") -> pd.DataFrame:
    """
    Extrai duas séries (valor e erro) alinhadas por data.
    Retorna dataframe com colunas: date, value, err
    """
    s_val = extract_series(dfi, date_cols_sorted, dates_ts_sorted, row_name=value_row)
    s_err = extract_series(dfi, date_cols_sorted, dates_ts_sorted, row_name=err_row)
    if s_val.empty and s_err.empty:
        return pd.DataFrame(columns=["date", "value", "err"])
    df = pd.merge(s_val.rename(columns={"value": "value"}),
                  s_err.rename(columns={"value": "err"}),
                  on="date", how="left")
    return df

# ====== SUAVIZAÇÃO/REAMOSTRAGEM para linha ======
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

# ====== REAMOSTRAGEM para bar plot com erro ======
def resample_for_bar_with_error(df: pd.DataFrame,
                                freq_code: str,
                                agg: str,
                                err_mode: str = "Média") -> pd.DataFrame:
    """
    Reamostra a série para barras:
      - value: usa a agregação escolhida (média, mediana, máx, mín)
      - err:   consolida por período segundo err_mode:
               "Média" -> média simples
               "RMS"   -> raiz da média dos quadrados
               "Máx"   -> valor máximo no período
    """
    if df.empty:
        return df

    df2 = df.set_index("date").asfreq("D")
    agg_fn_map = {"média": "mean", "mediana": "median", "máx": "max", "mín": "min"}
    agg_fn = agg_fn_map.get(agg, "mean")

    # agrega valor
    val_series = getattr(df2["value"].resample(freq_code), agg_fn)()

    # agrega erro
    if "err" in df2.columns:
        if err_mode == "RMS":
            err_series = (df2["err"]**2).resample(freq_code).mean() ** 0.5
        elif err_mode == "Máx":
            err_series = df2["err"].resample(freq_code).max()
        else:  # "Média"
            err_series = df2["err"].resample(freq_code).mean()
    else:
        err_series = pd.Series(index=val_series.index, dtype=float)

    out = pd.concat([val_series, err_series], axis=1).rename(columns={"value": "value", "err": "err"})
    out = out.dropna(subset=["value"])
    return out.reset_index()

# =============== Fluxo principal ===============
if uploaded is None:
    st.info("Faça o upload do seu Excel (`.xlsx`) no painel lateral.")
    st.stop()

try:
    book = read_excel_from_bytes(uploaded)
except Exception as e:
    st.error(f"Falha ao ler o Excel enviado. Detalhe: {e}")
    st.stop()

# Cada aba = 1 site
book = {name: normalize_cols(df.copy()) for name, df in book.items()}
site_names = sorted(book.keys())

# =================== MODO: 1 SITE vs VÁRIOS (SUBPLOTS) ===================
st.markdown("#### Modo de visualização")
compare_mode = st.toggle(
    "Comparar vários sites (subplots)",
    value=False,
    help="Quando ligado, plota uma grade com 1 gráfico por site (1 aba = 1 site)."
)

if compare_mode:
    chosen_sites = st.multiselect("Selecione os sites a comparar", site_names, default=site_names)
    if not chosen_sites:
        st.info("Selecione ao menos um site para comparar.")
        st.stop()

    # monta subplots: 2 colunas (ou 1, se houver só um site)
    n = len(chosen_sites)
    cols = 2 if n > 1 else 1
    rows = int(np.ceil(n / cols))

    fig_grid = make_subplots(rows=rows, cols=cols,
                             subplot_titles=chosen_sites,
                             shared_xaxes=False, shared_yaxes=False)

    freq_code = {"Diário": "D", "Semanal": "W", "Mensal": "M", "Trimestral": "Q"}[freq]

    r = c = 1
    for sname in chosen_sites:
        df_site_i = book[sname].copy()

        # normalização e índice
        if df_site_i.columns[0] != "Parametro":
            df_site_i.columns = ["Parametro"] + list(df_site_i.columns[1:])
        df_site_i["Parametro"] = df_site_i["Parametro"].astype(str).str.strip()
        dfi_i = df_site_i.set_index("Parametro", drop=True)

        # datas ordenadas
        date_cols_i, labels_i, stamps_i = extract_dates_from_first_row(df_site_i)
        order_i = sorted(
            range(len(date_cols_i)),
            key=lambda i: (pd.Timestamp.min if pd.isna(stamps_i[i]) else stamps_i[i])
        )
        date_cols_sorted_i = [date_cols_i[i] for i in order_i]
        stamps_sorted_i    = [stamps_i[i] for i in order_i]

        # série bruta da "Taxa Metano" e pós-processamento
        s_raw_i = extract_series(dfi_i, date_cols_sorted_i, stamps_sorted_i, row_name="Taxa Metano")
        s_proc_i = resample_and_smooth(s_raw_i, freq_code=freq_code, agg=agg, smooth=smooth, window=window)

        # adiciona cada subplot
        if not s_proc_i.empty:
            fig_grid.add_trace(
                go.Scatter(x=s_proc_i["date"], y=s_proc_i["value"], mode="lines+markers",
                           name=sname, showlegend=False),
                row=r, col=c
            )
        else:
            fig_grid.add_trace(
                go.Scatter(x=[], y=[], mode="markers", showlegend=False),
                row=r, col=c
            )

        # avança posição na grade
        c += 1
        if c > cols:
            c = 1
            r += 1

    fig_grid.update_layout(
        template="plotly_white",
        height=max(320, 260 * rows),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    # rótulos padronizados (cada subplot mostra eixo próprio)
    for i in range(1, rows * cols + 1):
        fig_grid.update_xaxes(title_text="Data", row=(i - 1) // cols + 1, col=(i - 1) % cols + 1)
        fig_grid.update_yaxes(title_text="Taxa de Metano", row=(i - 1) // cols + 1, col=(i - 1) % cols + 1)

    st.markdown("### Comparação por site (1 aba = 1 site)")
    st.plotly_chart(fig_grid, use_container_width=True)

    # neste modo, apenas comparamos — não mostramos detalhe nem PDF
    st.stop()

# =================== (fluxo normal — 1 SITE) ===================
# Seleção de site e data
site = st.selectbox("Selecione o Site", site_names)
df_site = book[site]
date_cols, labels, stamps = extract_dates_from_first_row(df_site)
order = sorted(range(len(date_cols)), key=lambda i: (pd.Timestamp.min if pd.isna(stamps[i]) else stamps[i]))
date_cols_sorted = [date_cols[i] for i in order]
labels_sorted = [labels[date_cols[i]] for i in order]
stamps_sorted = [stamps[i] for i in order]

selected_label = st.selectbox("Selecione a data", labels_sorted)
selected_col = date_cols_sorted[labels_sorted.index(selected_label)]

# Layout
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
            m = folium.Map(location=[float(rec["_lat"]), float(rec["_long"])], zoom_start=13, tiles="OpenStreetMap")
            folium.Marker([float(rec["_lat"]), float(rec["_long"])], tooltip=site).add_to(m)
            st_folium(m, height=400, use_container_width=True)

with right:
    st.subheader("Detalhes do Registro")
    dfi = df_site.copy()
    if dfi.columns[0] != "Parametro":
        dfi.columns = ["Parametro"] + list(dfi.columns[1:])
    dfi["Parametro"] = dfi["Parametro"].astype(str).str.strip()
    dfi = dfi.set_index("Parametro", drop=True)

    # -------- getv robusto (ignora acentos + aceita aliases) --------
    import unicodedata, re
    def _norm_txt(s: str) -> str:
        if s is None: return ""
        s = unicodedata.normalize("NFKD", str(s))
        s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("M"))
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s
    _index_norm = {_norm_txt(ix): ix for ix in dfi.index}

    def getv(name: str, *aliases):
        keys = [_norm_txt(name)] + [_norm_txt(a) for a in aliases]
        for k in keys:
            if k in _index_norm:
                return dfi.loc[_index_norm[k], selected_col]
        # fallback: início equivalente
        for nk, orig in _index_norm.items():
            if any(nk.startswith(k) for k in keys if k):
                return dfi.loc[orig, selected_col]
        return None
    # ----------------------------------------------------------------

    k1, k2, k3 = st.columns(3)
    k1.metric("Taxa Metano", f"{getv('Taxa Metano')}" if pd.notna(getv('Taxa Metano')) else "—")
    k2.metric("Incerteza", f"{getv('Incerteza')}" if pd.notna(getv('Incerteza')) else "—")
    k3.metric("Vento", f"{getv('Velocidade do Vento')}" if pd.notna(getv('Velocidade do Vento')) else "—")

    st.markdown("---")
    st.caption("Tabela completa (parâmetro → valor):")
    table_df = dfi[[selected_col]].copy()
    table_df.columns = ["Valor"]
    if "Imagem" in table_df.index: table_df = table_df.drop(index="Imagem")
    table_df = table_df.applymap(lambda v: "" if (pd.isna(v)) else str(v))
    st.dataframe(table_df, use_container_width=True)

# --------- Gráficos (Plotly) ---------
st.markdown("### Série temporal — Taxa de Metano (site)")

series_raw = extract_series(dfi, date_cols_sorted, stamps_sorted)
freq_code = {"Diário":"D","Semanal":"W","Mensal":"M","Trimestral":"Q"}[freq]
series = resample_and_smooth(series_raw, freq_code, agg, smooth, window)

fig_line = None
if not series.empty:
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(x=series["date"], y=series["value"], mode="lines+markers", name="Taxa Metano"))
    if show_conf and len(series) >= 3:
        p10 = series["value"].quantile(0.10); p90 = series["value"].quantile(0.90)
        fig_line.add_trace(go.Scatter(
            x=pd.concat([series["date"], series["date"][::-1]]),
            y=pd.concat([pd.Series([p90]*len(series)), pd.Series([p10]*len(series))[::-1]]),
            fill='toself', opacity=0.15, line=dict(width=0), name="P10–P90"
        ))
    if show_trend and len(series) >= 2:
        x = (series["date"] - series["date"].min()).dt.days.values.astype(float)
        yvals = series["value"].values.astype(float)
        coeffs = np.polyfit(x, yvals, 1); line = np.poly1d(coeffs)
        fig_line.add_trace(go.Scatter(x=series["date"], y=line(x), mode="lines", name="Tendência", line=dict(dash="dash")))
    fig_line.update_layout(template="plotly_white", xaxis_title="Data", yaxis_title="Taxa de Metano",
                           margin=dict(l=10, r=10, t=30, b=10), height=380)
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("Sem dados numéricos para a série temporal.")

# --------- Bar plot com barras de erro ---------
fig_bar = None
if show_bar:
    st.markdown("### Bar plot — Taxa de Metano com barras de erro (site)")

    series_valerr_raw = extract_series_pair(
        dfi, date_cols_sorted, stamps_sorted,
        value_row="Taxa Metano", err_row="Incerteza"
    )

    if not series_valerr_raw.empty:
        series_valerr = resample_for_bar_with_error(
            series_valerr_raw, freq_code=freq_code, agg=agg, err_mode=err_mode
        )

        if not series_valerr.empty:
            fig_bar = go.Figure()
            fig_bar.add_trace(
                go.Bar(
                    x=series_valerr["date"],
                    y=series_valerr["value"],
                    name="Taxa Metano",
                    error_y=dict(
                        type="data",
                        array=series_valerr["err"].fillna(0),
                        visible=True,
                        thickness=1.0
                    )
                )
            )
            fig_bar.update_layout(
                template="plotly_white",
                xaxis_title="Data",
                yaxis_title="Taxa de Metano",
                margin=dict(l=10, r=10, t=30, b=10),
                height=380
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Sem dados suficientes (após agregação) para o bar plot.")
    else:
        st.info("Sem dados de 'Taxa Metano' e/ou 'Incerteza' para montar o bar plot.")

# Boxplots + média mensal
st.markdown("### Boxplots por mês + média mensal (site)")
fig_box = None
if not series_raw.empty:
    dfm = series_raw.copy()
    dfm["month"] = dfm["date"].dt.to_period("M").dt.to_timestamp()
    order_months = sorted(dfm["month"].unique())
    fig_box = go.Figure()
    for m in order_months:
        vals = dfm.loc[dfm["month"] == m, "value"]
        fig_box.add_trace(go.Box(y=vals, name=m.strftime("%Y-%m"), boxmean="sd"))
    mean_by_month = dfm.groupby("month")["value"].mean().reindex(order_months)
    fig_box.add_trace(go.Scatter(x=[m.strftime("%Y-%m") for m in order_months],
                                 y=mean_by_month.values, mode="lines+markers", name="Média mensal"))
    fig_box.update_layout(template="plotly_white", yaxis_title="Taxa de Metano",
                          margin=dict(l=10, r=10, t=30, b=10), height=420, boxmode="group")
    st.plotly_chart(fig_box, use_container_width=True)
else:
    st.info("Sem dados suficientes para boxplots mensais.")

# ===================== PDF helpers =====================
def _image_reader_from_url(url: str):
    try:
        with urlopen(url, timeout=10) as resp:
            img = ImageReader(resp); w, h = img.getSize(); return img, w, h
    except Exception:
        return None, 0, 0

def _draw_logo_scaled(c, x_right, y_top, logo_img, lw, lh, max_w=90, max_h=42):
    if not logo_img: return 0, 0
    scale = min(max_w/lw, max_h/lh)
    w, h = lw*scale, lh*scale
    c.drawImage(logo_img, x_right - w, y_top - h, width=w, height=h, mask='auto')
    return w, h

# ====== PDF (Header Band, UTC) ======
def build_report_pdf(site, date, taxa, inc, vento, img_url, fig1, fig2,
                     logo_rel_path: str = LOGO_REL_PATH,
                     satellite: Optional[str] = None) -> bytes:
    # Cores (RGB 0..1)
    BAND   = (0x15/255, 0x5E/255, 0x75/255)   # #155E75
    ACCENT = (0xF5/255, 0x9E/255, 0x0B/255)   # #F59E0B
    GRAY   = (0x6B/255, 0x72/255, 0x80/255)   # #6B7280

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin = 40
    band_h = 80

    # carrega logo (via URL padrão do repositório)
    logo_url = f"{DEFAULT_BASE_URL.rstrip('/')}/{logo_rel_path.lstrip('/')}"
    logo_img, logo_w, logo_h = _image_reader_from_url(logo_url)

    page_no = 0
    def start_page():
        nonlocal page_no
        page_no += 1

        # faixa superior
        c.setFillColorRGB(*BAND)
        c.rect(0, H-band_h, W, band_h, fill=1, stroke=0)

        # logo na faixa
        _draw_logo_scaled(c, x_right=W - margin, y_top=H - (band_h/2 - 14),
                          logo_img=logo_img, lw=logo_w, lh=logo_h, max_w=90, max_h=42)

        # timestamp UTC
        ts_utc = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')

        # título/subtítulo
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, H - band_h + 28, "Relatório Geoportal de Metano")
        c.setFont("Helvetica", 10)
        c.drawString(
            margin, H - band_h + 12,
            f"Site: {site}   |   Data: {date}   |   Gerado em: {ts_utc}"
        )

        # separador cor de acento
        c.setFillColorRGB(0, 0, 0)
        c.setStrokeColorRGB(*ACCENT); c.setLineWidth(1)
        c.line(margin, H - band_h - 6, W - margin, H - band_h - 6)
        c.setStrokeColorRGB(0, 0, 0)

        return H - band_h - 20

    # primeira página
    y = start_page()

    def _s(v): return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)

    # Métricas
    c.setFont("Helvetica-Bold", 12); c.drawString(margin, y, "Métricas"); y -= 16
    c.setFont("Helvetica", 11)
    for line in (
        f"• Taxa Metano: {_s(taxa)}",
        f"• Incerteza: {_s(inc)}",
        f"• Velocidade do Vento: {_s(vento)}",
        f"• Satélite: {_s(satellite)}"
    ):
        c.drawString(margin, y, line); y -= 14
    y -= 10
    c.setStrokeColorRGB(*ACCENT); c.setLineWidth(0.7)
    c.line(margin, y, W - margin, y); y -= 14
    c.setStrokeColorRGB(0, 0, 0)

    # Imagem principal
    if img_url:
        main_img, iw, ih = _image_reader_from_url(img_url)
        if main_img:
            max_w, max_h = W - 2*margin, 190
            s = min(max_w/iw, max_h/ih); w, h = iw*s, ih*s
            if y - h < margin + 30:
                c.showPage(); y = start_page()
            c.drawImage(main_img, margin, y - h, width=w, height=h, mask='auto'); y -= h + 18

    # Gráfico 1
    if fig1 is not None:
        try:
            png1 = fig1.to_image(format="png", width=1400, height=800, scale=2, engine="kaleido")
            img1 = ImageReader(io.BytesIO(png1)); iw, ih = img1.getSize()
            max_w, max_h = W - 2*margin, 260
            s = min(max_w/iw, max_h/ih); w, h = iw*s, ih*s
            if y - h < margin + 30:
                c.showPage(); y = start_page()
            c.drawImage(img1, margin, y - h, width=w, height=h, mask='auto'); y -= h + 16
        except Exception as e:
            c.setFont("Helvetica", 9); c.drawString(margin, y, f"[Falha ao exportar gráfico 1: {e}]"); y -= 14

    # Gráfico 2
    if fig2 is not None:
        try:
            png2 = fig2.to_image(format="png", width=1400, height=900, scale=2, engine="kaleido")
            img2 = ImageReader(io.BytesIO(png2)); iw2, ih2 = img2.getSize()
            max_w, max_h = W - 2*margin, 260
            s2 = min(max_w/iw2, max_h/ih2); w2, h2 = iw2*s2, ih2*s2
            if y - h2 < margin + 30:
                c.showPage(); y = start_page()
            c.drawImage(img2, margin, y - h2, width=w2, height=h2, mask='auto'); y -= h2 + 12
        except Exception as e:
            c.setFont("Helvetica", 9); c.drawString(margin, y, f"[Falha ao exportar gráfico 2: {e}]"); y -= 14

    # Rodapé (pág X)
    c.setFont("Helvetica", 8); c.setFillColorRGB(*GRAY)
    c.drawRightString(W - margin, 12, f"pág {page_no}")
    c.setFillColorRGB(0, 0, 0)

    c.showPage(); c.save(); buf.seek(0)
    return buf.getvalue()

# ===================== Exportar PDF (UI) =====================
# Usa as variáveis calculadas acima (dfi/rec etc.)

def _get_from_dfi(dfi: pd.DataFrame, selected_col: str, name: str, *aliases):
    import unicodedata, re
    def _norm_txt(s: str) -> str:
        s = unicodedata.normalize("NFKD", str(s))
        s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("M"))
        return re.sub(r"\s+", " ", s).strip().lower()
    idx_norm = {_norm_txt(ix): ix for ix in dfi.index}
    keys = [_norm_txt(name)] + [_norm_txt(a) for a in aliases]
    for k in keys:
        if k in idx_norm:
            return dfi.loc[idx_norm[k], selected_col]
    for nk, orig in idx_norm.items():
        if any(nk.startswith(k) for k in keys if k):
            return dfi.loc[orig, selected_col]
    return None

taxa      = _get_from_dfi(dfi, selected_col, "Taxa Metano")
inc       = _get_from_dfi(dfi, selected_col, "Incerteza")
vento     = _get_from_dfi(dfi, selected_col, "Velocidade do Vento")
satellite = _get_from_dfi(dfi, selected_col, "Satelite", "Satélite", "Satellite", "Sat")
img_url   = resolve_image_target(rec.get("Imagem"))

st.markdown("---")
st.subheader("📄 Exportar PDF")
st.caption("Relatório com faixa superior (Header Band), logo, métricas (inclui Satélite), imagem e gráficos atuais. Timestamp em UTC.")

if st.button("Gerar PDF (dados + gráficos)", type="primary", use_container_width=True):
    pdf_bytes = build_report_pdf(
        site=site, date=selected_label, taxa=taxa, inc=inc, vento=vento,
        img_url=img_url,
        fig1=fig_line if 'fig_line' in locals() else None,
        fig2=fig_bar if ('fig_bar' in locals() and fig_bar is not None and show_bar) else (fig_box if 'fig_box' in locals() else None),
        logo_rel_path=LOGO_REL_PATH, satellite=satellite
    )
    st.download_button(
        label="⬇️ Baixar PDF",
        data=pdf_bytes,
        file_name=f"relatorio_geoportal_{site}_{selected_label}.pdf".replace(" ", "_"),
        mime="application/pdf",
        use_container_width=True
    )
