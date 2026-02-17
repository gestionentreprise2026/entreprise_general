from utils import apply_base_ui
apply_base_ui()

import streamlit as st
import pandas as pd
import bcrypt

from auth import require_login, sidebar_session, require_roles
from ge_db import listar_roles, listar_usuarios, crear_usuario, set_usuario_activo, reset_password

# ✅ 1) Login primero (SIEMPRE)
require_login()
sidebar_session()

# ✅ 2) Protección por rol (solo ADMIN)
require_roles("ADMIN")


# ✅ 3) Fuente de verdad del usuario logueado
user = st.session_state.auth
rol = user.get("rol", st.session_state.get("rol", "CONSULTA"))

st.title("👤 Gestión de Usuarios")

# --- Crear usuario ---
st.subheader("➕ Crear usuario")

roles = listar_roles()
roles_map = {r["nombre"]: r["id"] for r in roles}
rol_sel = st.selectbox("Rol", list(roles_map.keys()), index=0, key="usr_rol_sel")

c1, c2, c3 = st.columns(3)
with c1:
    username = st.text_input("Usuario (login)", placeholder="ej: admin", key="usr_username")
with c2:
    nombre = st.text_input("Nombre", placeholder="ej: Administrador", key="usr_nombre")
with c3:
    activo = st.selectbox("Activo", ["Sí", "No"], index=0, key="usr_activo")

pass1 = st.text_input("Contraseña", type="password", key="usr_pass1")
pass2 = st.text_input("Repetir contraseña", type="password", key="usr_pass2")

if st.button("Crear usuario", type="primary", key="usr_crear_btn"):
    if not username.strip():
        st.error("El usuario (login) es obligatorio.")
        st.stop()

    if pass1 != pass2 or not pass1:
        st.error("Las contraseñas no coinciden o están vacías.")
        st.stop()

    pwd_hash = bcrypt.hashpw(pass1.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    crear_usuario(
        username=username.strip(),
        nombre=nombre.strip() if nombre else None,
        password_hash=pwd_hash,
        rol_id=roles_map[rol_sel],
        activo=1 if activo == "Sí" else 0
    )

    st.success("✅ Usuario creado.")
    st.rerun()

st.divider()

# --- Listado ---
st.subheader("📋 Usuarios")

users = listar_usuarios()
df = pd.DataFrame(users) if users else pd.DataFrame(columns=["id", "username", "nombre", "rol", "activo"])
st.dataframe(df, use_container_width=True)

# --- Acciones ---
st.subheader("⚙️ Acciones")

if df.empty:
    st.info("No hay usuarios.")
    st.stop()

user_id = st.selectbox("Selecciona un usuario por ID", df["id"].tolist(), key="usr_user_id")

u = df[df["id"] == user_id].iloc[0].to_dict()
st.write(f"**Usuario:** {u['username']} | **Rol:** {u['rol']} | **Activo:** {u['activo']}")

c1, c2 = st.columns(2)

with c1:
    st.markdown("### ✅ Activar / Desactivar")
    nuevo_estado = st.selectbox("Estado", ["Activar", "Desactivar"], index=0, key="usr_estado_sel")
    if st.button("Aplicar estado", key="usr_estado_btn"):
        set_usuario_activo(user_id, 1 if nuevo_estado == "Activar" else 0)
        st.success("✅ Estado actualizado.")
        st.rerun()

with c2:
    st.markdown("### 🔑 Reset de contraseña")
    np1 = st.text_input("Nueva contraseña", type="password", key="usr_np1")
    np2 = st.text_input("Repetir nueva contraseña", type="password", key="usr_np2")
    if st.button("Resetear contraseña", key="usr_reset_btn"):
        if np1 != np2 or not np1:
            st.error("Las contraseñas no coinciden o están vacías.")
            st.stop()

        new_hash = bcrypt.hashpw(np1.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        reset_password(user_id, new_hash)
        st.success("✅ Contraseña actualizada.")
        st.rerun()
