# pages/login.py
import streamlit as st
from utils import apply_base_ui
from login_view import login_screen

st.set_page_config(page_title="Login", layout="centered", initial_sidebar_state="collapsed")
apply_base_ui(hide_nav=True)
login_screen()
