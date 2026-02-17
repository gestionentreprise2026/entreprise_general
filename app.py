import streamlit as st
from auth import require_login, sidebar_session
from utils import apply_base_ui

st.set_page_config(page_title="GESTION ENTERPRISE", layout="wide")

require_login()
apply_base_ui(hide_nav=False)  # ✅ ya logueado => mostrar menú
sidebar_session()

st.markdown("""
<style>
.topbar {background:#334155; padding:12px 18px; border-radius:10px; color:white; font-weight:600;}
</style>
<div class="topbar">GESTION ENTERPRISE</div>
""", unsafe_allow_html=True)

st.title("🏠 Inicio")
st.info("Selecciona una opción en el menú de la izquierda (páginas).")
