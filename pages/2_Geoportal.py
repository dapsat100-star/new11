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

# Fallback de renderização do gráfico para o PDF (Matplotlib)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ----------------- Página -----------------
st.set_page_config(page_title="Geoportal — Metano", layout="wide", initial_sidebar_state="expanded")

# === CSS para UI (remove menu multipágina padrão) ===
st.markdown(
    """
<style>
/* Esconde o cabeçalho nativo */
header[data-testid="stHeader"] { display: none !important; }

/* Mantém a sidebar visível (seu conteúdo customizado) */
section[data-testid="stSidebar"], aside[data-testid="stSidebar"] {
  display: block !important; transform: none !important; visibility: visible !important;
}
div[data-testid="collapsedControl"]{ display:block !important; }

/* === REMOVE o menu multipágina padrão da sidebar === */
div[data-testid="stSidebarNav"] { display: none !important; }
/* Fallbacks para variações de versão */
section[data-testid="stSidebar"] nav { display: none !important; }
section[data-testid="stSidebar"] [role="navigation"] { display: none !important; }

/* Logo no topo-direito */
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

# ---- Link único na sidebar (opcional) ----
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
    """Busca valor por nome do parâmetro (case/acento-insensitive)."""
    import unicodedata, re
    def _norm_txt(s)->str:
        if s is None or (isinstance(s,float) and pd.isna(s)): return ""
        s=unicodedata.normalize("NFKD",str(s))
        s="".join(ch for ch in s if not unicodedata.category(ch).startswith("M"))
        return re.sub(r"\s+"," ",s).strip().lower()
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
order = sorted(range(len(date_cols)), key=lambda i: (pd.Timestamp.min if pd.isna(stamps[i]) else stamps[i]))
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
    v_taxa  = get_from_dfi(dfi, selected_col, "Taxa Metano")
    v_inc   = get_from_dfi(dfi, selected_col, "Incerteza")
    v_vento = get_from_dfi(dfi, selected_col, "Velocidade do Vento")

    k1.metric("Taxa Metano", f"{v_taxa}" if pd.notna(v_taxa) else "—")
    k2.metric("Incerteza", f"{v_inc}" if pd.notna(v_inc) else "—")
    k3.metric("Vento", f"{v_vento}" if pd.notna(v_vento) else "—")

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
    # Salva contexto para fallback no PDF
    st.session_state["_plot_ctx"] = {
        "x": df_plot["date"].tolist(),
        "y": df_plot["metano"].tolist(),
        "yerr": err_array.tolist(),
        "show_unc_bars": bool(show_unc_bars),
        "show_trend": bool(show_trend),
    }
    line_kwargs = {"shape": "spline"} if line_spline else {}

    fig_line = go.Figure()
    fig_line.add_trace(
        go.Scatter(
            x=df_plot["date"],
            y=df_plot["metano"],
            mode="lines+markers",
            name="Taxa de Metano",
            line=dict(**line_kwargs),
            error_y=dict(type="data", array=err_array, visible=bool(show_unc_bars), thickness=1.2, width=3),
        )
    )

    if show_trend and len(df_plot) >= 2:
        x = (df_plot["date"] - df_plot["date"].min()).dt.days.values.astype(float)
        y = df_plot["metano"].values.astype(float)
        coeffs = np.polyfit(x, y, 1)
        line = np.poly1d(coeffs)
        fig_line.add_trace(
            go.Scatter(x=df_plot["date"], y=line(x), mode="lines", name="Tendência", line=dict(dash="dash"))
        )

    fig_line.update_layout(
        template="plotly_white", xaxis_title="Data", yaxis_title="Taxa de Metano",
        margin=dict(l=10, r=10, t=30, b=10), height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ===================== PDF helpers =====================

def _image_reader_from_url(url: str):
    try:
        with urlopen(url, timeout=10) as resp:
            img = ImageReader(resp); w, h = img.getSize()
            return img, w, h
    except Exception:
        return None, 0, 0

def _draw_logo_scaled(c, x_right, y_top, logo_img, lw, lh, max_w=90, max_h=42):
    if not logo_img: return 0, 0
    scale = min(max_w / lw, max_h / lh)
    w, h = lw * scale, lh * scale
    c.drawImage(logo_img, x_right - w, y_top - h, width=w, height=h, mask='auto')
    return w, h

def _export_fig_to_png_bytes(fig) -> Optional[bytes]:
    """Exporta figura Plotly para PNG.
    1) plotly.io + kaleido; 2) kaleido PlotlyScope; 3) Matplotlib (fallback)."""
    # 1) Plotly + kaleido
    try:
        import plotly.io as pio
        return pio.to_image(fig, format="png", width=1400, height=800, scale=2, engine="kaleido")
    except Exception:
        pass
    # 2) PlotlyScope
    try:
        from kaleido.scopes.plotly import PlotlyScope
        scope = PlotlyScope(plotlyjs=None, mathjax=False)
        return scope.transform(fig.to_plotly_json(), format="png", width=1400, height=800, scale=2)
    except Exception:
        pass
    # 3) Matplotlib fallback usando o contexto salvo
    try:
        ctx = st.session_state.get("_plot_ctx")
        if not ctx:
            return None
        x = pd.to_datetime(pd.Series(ctx.get("x", [])))
        y = pd.to_numeric(pd.Series(ctx.get("y", [])), errors="coerce")
        yerr = pd.to_numeric(pd.Series(ctx.get("yerr", [])), errors="coerce").fillna(0)
        show_unc = bool(ctx.get("show_unc_bars", True))
        show_tr = bool(ctx.get("show_trend", False))
        if x.empty or y.empty:
            return None
        fig_m, ax = plt.subplots(figsize=(14, 8), dpi=100)
        ax.plot(x, y, marker="o", linewidth=2)
        if show_unc:
            ax.errorbar(x, y, yerr=yerr, fmt='none', linewidth=1)
        if show_tr and len(x) >= 2:
            xd = (x - x.min()).dt.days.astype(float).to_numpy()
            coeffs = np.polyfit(xd, y.to_numpy(dtype=float), 1)
            yhat = np.poly1d(coeffs)(xd)
            ax.plot(x, yhat, linestyle='--')
        ax.set_xlabel("Data"); ax.set_ylabel("Taxa de Metano")
        fig_m.autofmt_xdate()
        buf = io.BytesIO()
        fig_m.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig_m)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

def build_report_pdf(
    site,
    date,
    taxa,
    inc,
    vento,
    img_url,
    fig1,
    logo_rel_path: str = LOGO_REL_PATH,
    satellite: Optional[str] = None,
) -> bytes:
    BAND   = (0x15/255, 0x5E/255, 0x75/255)
    ACCENT = (0xF5/255, 0x9E/255, 0x0B/255)
    GRAY   = (0x6B/255, 0x72/255, 0x80/255)

    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin = 40
    band_h = 80

    logo_url = f"{DEFAULT_BASE_URL.rstrip('/')}/{logo_rel_path.lstrip('/')}"
    logo_img, logo_w, logo_h = _image_reader_from_url(logo_url)

    page_no = 0
    def start_page():
        nonlocal page_no
        page_no += 1
        c.setFillColorRGB(*BAND)
        c.rect(0, H - band_h, W, band_h, fill=1, stroke=0)
        _draw_logo_scaled(c, x_right=W - margin, y_top=H - (band_h/2 - 14),
                          logo_img=logo_img, lw=logo_w, lh=logo_h, max_w=90, max_h=42)
        ts_utc = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
        c.setFillColorRGB(1,1,1); c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, H - band_h + 28, "Relatório Geoportal de Metano")
        c.setFont("Helvetica", 10)
        c.drawString(margin, H - band_h + 12, f"Site: {site}   |   Data: {date}   |   Gerado em: {ts_utc}")
        c.setFillColorRGB(0,0,0)
        c.setStrokeColorRGB(*ACCENT); c.setLineWidth(1)
        c.line(margin, H - band_h - 6, W - margin, H - band_h - 6)
        c.setStrokeColorRGB(0,0,0)
        return H - band_h - 20

    y = start_page()

    def _s(v): return "—" if v is None or (isinstance(v,float) and pd.isna(v)) else str(v)

    # Métricas
    c.setFont("Helvetica-Bold", 12); c.drawString(margin, y, "Métricas"); y -= 16
    c.setFont("Helvetica", 11)
    for line in (
        f"• Taxa Metano: {_s(taxa)}",
        f"• Incerteza: {_s(inc)}",
        f"• Velocidade do Vento: {_s(vento)}",
        f"• Satélite: {_s(satellite)}",
    ):
        c.drawString(margin, y, line); y -= 14

    y -= 10; c.setStrokeColorRGB(*ACCENT); c.setLineWidth(0.7)
    c.line(margin, y, W - margin, y); y -= 14; c.setStrokeColorRGB(0,0,0)

    # Figura 1 — Imagem principal (se houver) + LEGENDA
    if img_url:
        main_img, iw, ih = _image_reader_from_url(img_url)
        if main_img:
            max_w, max_h = W - 2*margin, 190
            s = min(max_w/iw, max_h/ih); w, h = iw*s, ih*s
            if y - h < margin + 30:
                c.showPage(); y = start_page()
            c.drawImage(main_img, margin, y - h, width=w, height=h, mask='auto')
            # legenda da Figura 1
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(margin, y - h - 12, "Figura 1 - Concentração de Metano em ppb")
            y -= h + 26

    # Figura 2 — Gráfico + LEGENDA
    if fig1 is not None:
        try:
            png1 = _export_fig_to_png_bytes(fig1)
            if png1 is None:
                raise RuntimeError("Exportação PNG indisponível no ambiente")
            img1 = ImageReader(io.BytesIO(png1))
            iw, ih = img1.getSize()
            max_w, max_h = W - 2*margin, 260
            s = min(max_w/iw, max_h/ih); w, h = iw*s, ih*s
            if y - h < margin + 30:
                c.showPage(); y = start_page()
            c.drawImage(img1, margin, y - h, width=w, height=h, mask='auto')
            # legenda da Figura 2
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(margin, y - h - 12, "Figura 2 - Série Histórica de Concentração de Metano")
            y -= h + 26
        except Exception as e:
            c.setFont("Helvetica", 9)
            c.drawString(margin, y, f"[Falha ao exportar gráfico: {e}]"); y -= 14

    # Rodapé
    c.setFont("Helvetica", 8); c.setFillColorRGB(*GRAY)
    c.drawRightString(W - margin, 12, f"pág {page_no}")
    c.setFillColorRGB(0,0,0)

    c.showPage(); c.save(); buf.seek(0)
    return buf.getvalue()

# ===================== Exportar PDF (UI) =====================

with right:
    taxa      = get_from_dfi(dfi, selected_col, "Taxa Metano")
    inc       = get_from_dfi(dfi, selected_col, "Incerteza")
    vento     = get_from_dfi(dfi, selected_col, "Velocidade do Vento")
    satellite = get_from_dfi(dfi, selected_col, "Satelite", "Satélite", "Satellite", "Sat")

img_url = resolve_image_target(rec.get("Imagem"))

st.markdown("---")
st.subheader("📄 Exportar PDF")
st.caption("Relatório com faixa superior, logo, métricas, imagem e o gráfico atual (linha + barras de incerteza). Timestamp em UTC.")

if st.button("Gerar PDF (dados + gráfico)", type="primary", use_container_width=True):
    pdf_bytes = build_report_pdf(
        site=site, date=selected_label, taxa=taxa, inc=inc, vento=vento,
        img_url=img_url, fig1=fig_line,
        logo_rel_path=LOGO_REL_PATH, satellite=satellite
    )
    st.download_button(
        label="⬇️ Baixar PDF",
        data=pdf_bytes,
        file_name=f"relatorio_geoportal_{site}_{selected_label}.pdf".replace(" ", "_"),
        mime="application/pdf",
        use_container_width=True
    )
