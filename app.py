import streamlit as st
from auth import require_login, sidebar_session
from utils import apply_base_ui

st.set_page_config(page_title="GESTION ENTERPRISE", layout="wide")

require_login()              # <- si no hay auth, manda al login y corta aquí

apply_base_ui(hide_nav=False)
sidebar_session()

st.title("🏠 Inicio")
st.info("Selecciona una opción en el menú de la izquierda (páginas).")
