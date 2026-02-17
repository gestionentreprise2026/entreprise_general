import streamlit as st
from ge_db import autenticar
from utils import apply_base_ui

def login_screen():
    st.set_page_config(page_title="Login", layout="wide")  # ✅ primero
    apply_base_ui(hide_nav=True)                           # ✅ después

    st.markdown(
        """
        <style>
        .login-card {
            max-width: 520px;
            margin: 60px auto;
            padding: 28px;
            border-radius: 16px;
            border: 1px solid #e5e7eb;
            background: white;
            box-shadow: 0 10px 24px rgba(0,0,0,.06);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown("## 🔐 Iniciar sesión")

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar", type="primary", key="login_btn"):
        user = autenticar(username, password)
        if user:
            st.session_state.auth = user
            st.session_state["rol"] = user.get("rol", "CONSULTA")
            st.session_state["user"] = user.get("usuario") or username
            st.session_state["rol_id"] = user.get("rol_id")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

    st.markdown("</div>", unsafe_allow_html=True)
