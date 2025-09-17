# ui_helpers.py
import streamlit as st

def hide_streamlit_chrome(hide_header=True, hide_toolbar=True, hide_sidebar_nav=False):
    st.markdown(
        f"""
        <style>
        {'header[data-testid="stHeader"] { display: none; }' if hide_header else ''}
        {'div[data-testid="stToolbar"] { display: none !important; }' if hide_toolbar else ''}
        {'div[data-testid="stSidebarNav"] { display: none !important; }' if hide_sidebar_nav else ''}
        </style>
        """,
        unsafe_allow_html=True,
    )
