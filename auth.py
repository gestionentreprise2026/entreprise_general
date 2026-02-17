import streamlit as st
from login import login_screen
from utils import apply_base_ui

def require_login():
    if "auth" not in st.session_state:
        st.session_state.auth = None

    if st.session_state.auth is None:
        apply_base_ui(hide_nav=True)   # ✅ ocultar menú multipágina en login
        login_screen()
        st.stop()

def require_roles(*roles):
    user = st.session_state.get("auth") or {}
    rol = user.get("rol", "CONSULTA")
    if rol not in roles:
        st.error("⛔ No tienes permisos para ver esta sección.")
        st.stop()

def sidebar_session():
    user = st.session_state.get("auth") or {}
    rol = user.get("rol", "CONSULTA")
    nombre = user.get("nombre") or user.get("usuario") or "Usuario"

    with st.sidebar:
        st.markdown("### 👤 Sesión")
        st.success(f"{nombre}\n\nRol: {rol}")
        st.divider()

        if st.button("Cerrar sesión", key="btn_logout"):
            st.session_state.clear()
            st.rerun()
