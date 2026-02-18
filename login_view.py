# login_view.py
import streamlit as st
from ge_db import autenticar

def login_screen():
    st.markdown("""
<style>
  /* Fondo */
  .stApp {
    background: #f1f5f9;
  }

  /* Centrado y ancho */
  .block-container{
    max-width: 600px !important;
    margin: 0 auto !important;
    padding-top: 10vh !important;
  }

  /* Container blanco sólido */
  div[data-testid="stVerticalBlockBorderWrapper"]{
    background: #ffffff !important;
    border-radius: 20px !important;
    border: 2px solid #e2e8f0 !important;
    box-shadow: 0 30px 60px rgba(0,0,0,.15) !important;
  }

  /* Padding interno */
  div[data-testid="stVerticalBlockBorderWrapper"] > div{
    padding: 32px !important;
  }

  /* Inputs */
  div[data-testid="stTextInput"] input{
    height: 46px !important;
    border-radius: 16px !important;
  }

  /* Botón */
  div[data-testid="stFormSubmitButton"] button{
    width: 100% !important;
    height: 46px !important;
    border-radius: 12px !important;
    font-weight: 800 !important;
  }

  .stTextInput { margin-bottom: 12px; }

  .login-app{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: .08em;
    color: #64748b;
    text-transform: uppercase;
    margin-bottom: 12px;
  }

  .login-title{
    font-size: 34px;
    font-weight: 900;
    margin: 0;
    color: #0f172a;
  }

  .login-sub{
    color: #64748b;
    margin-top: 8px;
    margin-bottom: 18px;
    font-size: 14px;
  }

  .login-foot{
    margin-top: 14px;
    font-size: 12px;
    color: #94a3b8;
    text-align: center;
  }
</style>
""", unsafe_allow_html=True)


    with st.container(border=True):
        st.markdown('<div class="login-app">GESTION ENTERPRISE</div>', unsafe_allow_html=True)

        st.markdown(
            '<div style="display:flex;gap:10px;align-items:center;">'
            '<div style="font-size:26px;">🔐</div>'
            '<div class="login-title">Iniciar sesión</div>'
            '</div>',
            unsafe_allow_html=True
        )
        st.markdown('<div class="login-sub">Accede con tu usuario y contraseña</div>', unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Usuario", placeholder="Usuario", label_visibility="collapsed")
            password = st.text_input("Contraseña", type="password", placeholder="Contraseña", label_visibility="collapsed")
            ok = st.form_submit_button("Entrar")

        if ok:
            user = autenticar(username, password)
            if user:
                st.session_state.auth = user
                st.session_state["rol"] = user.get("rol", "CONSULTA")
                st.session_state["user"] = user.get("usuario") or username
                st.session_state["rol_id"] = user.get("rol_id")
                st.switch_page("app.py")
            else:
                st.error("Usuario o contraseña incorrectos")

        st.markdown('<div class="login-foot">© 2026 Gestion Entreprise · v1.0</div>', unsafe_allow_html=True)
