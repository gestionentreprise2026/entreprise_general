import streamlit as st
from utils import apply_base_ui
from auth import require_login, sidebar_session

st.set_page_config(page_title="Movimientos", layout="wide")
apply_base_ui(hide_nav=False)   # ✅ aquí NO se oculta el menú (ya estás logueado)

import pandas as pd
import os
import re
from datetime import datetime
from io import BytesIO

from ge_db import (
    guardar_movimiento,
    listar_movimientos,
    obtener_movimiento,
    listar_detalle_movimiento,
    listar_clientes,
    listar_empresas,
    listar_bancos,
)

# ✅ 1) Login y sidebar primero
require_login()
sidebar_session()

# ✅ 2) Rol desde auth (fuente de verdad)
user = st.session_state.auth
rol = user.get("rol", "CONSULTA")

# ✅ 3) Protección por rol
if rol not in ["ADMIN", "ASISTENTE", "SOCIO"]:
    st.error("No tienes permisos para acceder a Movimientos.")
    st.stop()

st.title("Registro de Movimientos Varios")

# ... aquí sigue TODO tu código de movimientos ...


# ---------- Helpers ----------
def safe_filename(name: str) -> str:
    name = name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name or "archivo"

@st.cache_data(ttl=60)
def load_catalogos():
    clientes = listar_clientes()
    empresas = listar_empresas()
    bancos = listar_bancos()
    return clientes, empresas, bancos


# ---------- UI ----------
st.markdown(
    """
    <style>
    .topbar {background:#334155; padding:12px 18px; border-radius:10px; color:white; font-weight:600;}
    </style>
    <div class="topbar">GESTION ENTERPRISE</div>
    """,
    unsafe_allow_html=True,
)

st.write("")
st.caption("Movimientos / Registro de Movimientos Varios / Crear")

# ---------- Catálogos ----------
try:
    clientes_db, empresas_db, bancos_db = load_catalogos()
except Exception as e:
    st.error(f"No se pudo cargar catálogos desde la BD: {e}")
    clientes_db, empresas_db, bancos_db = [], [], []

clientes_map = {f'{c["nombre"]} (ID {c["id"]})': c["id"] for c in clientes_db}
empresas_map = {f'{e["nombre"]} (ID {e["id"]})': e["id"] for e in empresas_db}
bancos_map   = {f'{b["nombre"]} (ID {b["id"]})': b["id"] for b in bancos_db}

clientes_opts = ["Seleccione"] + list(clientes_map.keys())
empresas_opts = ["Seleccione"] + list(empresas_map.keys())
bancos_opts   = ["Seleccione"] + list(bancos_map.keys())

# Por ahora fijo; luego lo traemos de DB
cuentas = ["", "1010", "2020", "3030"]

# ---------- Registro ----------
st.subheader("Registro de Movimientos Varios")

col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
with col1:
    fecha_hora = st.text_input("Fecha y Hora", value=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
with col2:
    cliente_sel = st.selectbox("Cliente", clientes_opts)
with col3:
    empresa_sel = st.selectbox("Empresa", empresas_opts)
with col4:
    banco_sel = st.selectbox("Banco", bancos_opts)

cliente_id = clientes_map.get(cliente_sel)
empresa_id = empresas_map.get(empresa_sel)
banco_id = bancos_map.get(banco_sel)

st.markdown("### Detalle")

if "lineas" not in st.session_state:
    st.session_state.lineas = pd.DataFrame([{
        "Cuenta": "",
        "Descripción": "",
        "Débito": 0.0,
        "Crédito": 0.0,
        "Notas": ""
    }])

btn1, btn2, _ = st.columns([1, 1, 6])
with btn1:
    if st.button("Nuevo", key="mov_nuevo_linea"):
        st.session_state.lineas = pd.concat(
            [st.session_state.lineas,
             pd.DataFrame([{"Cuenta": "", "Descripción": "", "Débito": 0.0, "Crédito": 0.0, "Notas": ""}])],
            ignore_index=True
        )
with btn2:
    if st.button("Duplicar", key="mov_dup_linea"):
        st.session_state.lineas = pd.concat(
            [st.session_state.lineas, st.session_state.lineas.tail(1)],
            ignore_index=True
        )

edited = st.data_editor(
    st.session_state.lineas,
    width="stretch",
    num_rows="dynamic",
    column_config={
        "Cuenta": st.column_config.SelectboxColumn("Cuenta", options=cuentas),
        "Débito": st.column_config.NumberColumn("Débito", min_value=0.0, step=0.01),
        "Crédito": st.column_config.NumberColumn("Crédito", min_value=0.0, step=0.01),
    },
    key="mov_editor",
)
st.session_state.lineas = edited

# ---------- Archivos ----------
st.markdown("### Archivo por línea (simple)")
uploaded_files = []
for i in range(len(st.session_state.lineas)):
    f = st.file_uploader(f"Archivo línea {i+1}", key=f"mov_file_{i}")
    uploaded_files.append(f)

# ---------- Guardar ----------
st.write("")
if st.button("Enviar", type="primary", disabled=not puede_guardar, key="mov_enviar"):

    if cliente_sel == "Seleccione" or empresa_sel == "Seleccione" or banco_sel == "Seleccione":
        st.error("Seleccione Cliente, Empresa y Banco antes de guardar.")
        st.stop()

    if cliente_id is None or empresa_id is None or banco_id is None:
        st.error("No se pudieron resolver los IDs desde los catálogos.")
        st.stop()

    total_debito = float(st.session_state.lineas["Débito"].fillna(0).sum())
    total_credito = float(st.session_state.lineas["Crédito"].fillna(0).sum())

    if round(total_debito, 2) != round(total_credito, 2):
        st.error("No se puede guardar: el Total Débito debe ser igual al Total Crédito.")
        st.stop()

    os.makedirs("data/uploads", exist_ok=True)

    lineas = st.session_state.lineas.to_dict(orient="records")

    saved_paths = []
    for i, f in enumerate(uploaded_files):
        if f is None:
            saved_paths.append(None)
            continue

        original = safe_filename(f.name)
        unique_name = f"mov_{datetime.now().strftime('%Y%m%d_%H%M%S')}_linea_{i+1}_{original}"
        path = os.path.join("data", "uploads", unique_name)

        with open(path, "wb") as out:
            out.write(f.getbuffer())

        saved_paths.append(path)

    for i in range(len(lineas)):
        lineas[i]["archivo"] = saved_paths[i] if i < len(saved_paths) else None

    mov_id = guardar_movimiento(
        fecha_hora,
        cliente_sel,
        empresa_sel,
        banco_sel,
        total_debito,
        total_credito,
        lineas,
        cliente_id=cliente_id,
        empresa_id=empresa_id,
        banco_id=banco_id,
    )

    st.success(f"Movimiento guardado correctamente ✅ (ID {mov_id})")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ID", mov_id)
    c2.metric("Líneas", len(lineas))
    c3.metric("Total Débito", f"{total_debito:,.2f}")
    c4.metric("Total Crédito", f"{total_credito:,.2f}")

    with st.expander("Ver datos técnicos (debug)"):
        st.json({
            "fecha_hora": fecha_hora,
            "cliente": cliente_sel,
            "empresa": empresa_sel,
            "banco": banco_sel,
            "cliente_id": cliente_id,
            "empresa_id": empresa_id,
            "banco_id": banco_id,
            "lineas": lineas,
            "archivos": saved_paths,
            "total_debito": total_debito,
            "total_credito": total_credito,
            "id": mov_id
        })

    # Reset
    st.session_state.lineas = pd.DataFrame([{
        "Cuenta": "",
        "Descripción": "",
        "Débito": 0.0,
        "Crédito": 0.0,
        "Notas": ""
    }])

    for i in range(len(uploaded_files)):
        k = f"mov_file_{i}"
        if k in st.session_state:
            del st.session_state[k]

    st.rerun()

# ---------- Consulta ----------
st.divider()
st.subheader("Consulta")

f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
with f1:
    desde = st.date_input("Desde esta fecha", key="mov_desde")
with f2:
    hasta = st.date_input("Hasta esta fecha", key="mov_hasta")
with f3:
    filtro = st.selectbox("Filtro", ["Día", "Mes", "Año"], key="mov_filtro")
with f4:
    st.write("")
    consultar = st.button("Consultar", key="mov_consultar")

if consultar:
    rows = listar_movimientos(desde, hasta)
    demo = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["id", "Fecha", "Cliente", "Empresa", "Banco", "Débito", "Crédito", "Estado"]
    )
else:
    demo = pd.DataFrame(columns=["id", "Fecha", "Cliente", "Empresa", "Banco", "Débito", "Crédito", "Estado"])

st.dataframe(demo, width="stretch")

# Export Excel
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    demo.to_excel(writer, index=False, sheet_name="Movimientos")

st.download_button(
    label="Descargar Excel",
    data=buffer.getvalue(),
    file_name="movimientos.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    key="mov_excel"
)

# ---------- Detalle ----------
st.markdown("### Detalle del movimiento")

if not demo.empty:
    col_id = "id" if "id" in demo.columns else ("Id" if "Id" in demo.columns else None)
    if col_id:
        ids = demo[col_id].dropna().astype(int).tolist()
        mov_id_sel = st.selectbox("Selecciona un ID para ver detalle", ids, key="mov_id_sel")

        mov = obtener_movimiento(int(mov_id_sel))
        if mov:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ID", mov["id"])
            c2.metric("Cliente", mov.get("cliente", ""))
            c3.metric("Empresa", mov.get("empresa", ""))
            c4.metric("Banco", mov.get("banco", ""))

            c5, c6, _ = st.columns([2, 2, 4])
            c5.metric("Total Débito", f'{float(mov["total_debito"]):,.2f}')
            c6.metric("Total Crédito", f'{float(mov["total_credito"]):,.2f}')

            detalle = listar_detalle_movimiento(int(mov_id_sel))
            det_df = pd.DataFrame(detalle) if detalle else pd.DataFrame(
                columns=["Cuenta", "Descripción", "Débito", "Crédito", "Notas", "Archivo"]
            )
            st.dataframe(det_df, width="stretch")

            st.markdown("#### Archivos del movimiento")
            if not det_df.empty and "Archivo" in det_df.columns:
                for idx, row in det_df.iterrows():
                    path = row.get("Archivo")
                    if isinstance(path, str) and path:
                        try:
                            with open(path, "rb") as f:
                                st.download_button(
                                    label=f"Descargar archivo línea {idx+1}",
                                    data=f.read(),
                                    file_name=path.split("\\")[-1].split("/")[-1],
                                    mime="application/octet-stream",
                                    key=f"mov_dl_{mov_id_sel}_{idx}"
                                )
                        except Exception:
                            st.warning(f"No se pudo leer el archivo: {path}")
        else:
            st.info("No se encontró la cabecera del movimiento.")
    else:
        st.info("No encontré columna de ID en la tabla de consulta.")
else:
    st.info("No hay resultados para mostrar detalle. Usa 'Consultar' primero.")
