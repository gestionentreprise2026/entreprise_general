import streamlit as st

def apply_base_ui(hide_nav: bool = False):
    base = """
    header {visibility: hidden;}
    .block-container { padding-top: 2rem; }
    """

    hide = ""
    if hide_nav:
        hide = """
        /* Oculta sidebar y nav multipage */
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarNav"] { display: none !important; }
        section[data-testid="stSidebar"] nav { display: none !important; }

        /* Quita el espacio lateral */
        .stApp [data-testid="stAppViewContainer"] .main { margin-left: 0 !important; }

        /* Centra login */
        .block-container{
          max-width: 520px !important;
          margin: 0 auto !important;
          padding-top: 12vh !important;
        }
        """

    st.markdown(f"<style>{base}{hide}</style>", unsafe_allow_html=True)
