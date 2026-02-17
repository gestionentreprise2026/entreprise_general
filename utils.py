import streamlit as st

def apply_base_ui(hide_nav: bool = False):
    css = ""

    if hide_nav:
        css = """
        <style>
        [data-testid="stSidebarNav"] {display: none !important;}
        [data-testid="stSidebarNavSearch"] {display: none !important;}
        [data-testid="stSidebarNavItems"] {display: none !important;}
        [data-testid="stSidebarNavSeparator"] {display: none !important;}
        </style>
        """

    st.markdown(css, unsafe_allow_html=True)
