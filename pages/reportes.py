from utils import apply_base_ui
apply_base_ui()

import streamlit as st
from auth import require_login, require_roles, sidebar_session

st.set_page_config(page_title="Reportes", layout="wide")

require_login()
sidebar_session()
require_roles("ADMIN", "CONTADOR")

st.title("📈 Reportes")
st.info("Aquí haremos informes, métricas, exportaciones, etc.")
