import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
from io import BytesIO
from ge_db import guardar_movimiento, listar_movimientos, obtener_movimiento, listar_detalle_movimiento


def safe_filename(name: str) -> str:
    # Limpia el nombre para evitar caracteres raros en Windows
    name = name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name or "archivo"

st.set_page_config(page_title="GESTION ENTERPRISE", layout="wide")

# ----- Navbar simple -----
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

# ----- Datos demo (luego conectas a DB/API) -----
clientes = {"Seleccione": "", "Cliente 1": "1", "Cliente 2": "2"}
empresas = {"Seleccione": "", "Empresa A": "A", "Empresa B": "B"}
bancos = {"Seleccione": "", "Banco X": "X", "Banco Y": "Y"}
cuentas = ["", "1010", "2020", "3030"]

st.subheader("Registro de Movimientos Varios")

col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

with col1:
    fecha_hora = st.text_input("Fecha y Hora", value=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
with col2:
    cliente = st.selectbox("Cliente", list(clientes.keys()))
with col3:
    empresa = st.selectbox("Empresa", list(empresas.keys()))
with col4:
    banco = st.selectbox("Banco", list(bancos.keys()))

# ----- Tabla editable de líneas -----
st.markdown("### Detalle")

if "lineas" not in st.session_state:
    st.session_state.lineas = pd.DataFrame(
        [{
            "Cuenta": "",
            "Descripción": "",
            "Débito": 0.0,
            "Crédito": 0.0,
            "Notas": ""
        }]
    )

btn1, btn2, _ = st.columns([1, 1, 6])
with btn1:
    if st.button("Nuevo"):
        st.session_state.lineas = pd.concat(
            [st.session_state.lineas, pd.DataFrame([{"Cuenta": "", "Descripción": "", "Débito": 0.0, "Crédito": 0.0, "Notas": ""}])],
            ignore_index=True
        )
with btn2:
    if st.button("Duplicar"):
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
)

st.session_state.lineas = edited

# ----- Archivos por línea -----
st.markdown("### Archivo por línea (simple)")
uploaded_files = []
for i in range(len(st.session_state.lineas)):
    f = st.file_uploader(f"Archivo línea {i+1}", key=f"file_{i}")
    uploaded_files.append(f)

# ----- Enviar -----
st.write("")
if st.button("Enviar", type="primary"):

    # Totales
    total_debito = float(st.session_state.lineas["Débito"].fillna(0).sum())
    total_credito = float(st.session_state.lineas["Crédito"].fillna(0).sum())

    # Validación contable
    if round(total_debito, 2) != round(total_credito, 2):
        st.error("No se puede guardar: el Total Débito debe ser igual al Total Crédito.")
        st.stop()

    # Asegura carpeta de uploads
    os.makedirs("data/uploads", exist_ok=True)

    # Copia de líneas para agregar "archivo"
    lineas = st.session_state.lineas.to_dict(orient="records")

    # Guardar archivos y asignarlos a cada línea por índice
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

    # Poner la ruta guardada en cada línea
    for i in range(len(lineas)):
        lineas[i]["archivo"] = saved_paths[i] if i < len(saved_paths) else None

    payload = {
        "fecha_hora": fecha_hora,
        "cliente": cliente,
        "empresa": empresa,
        "banco": banco,
        "lineas": lineas,
        "archivos": saved_paths,
        "total_debito": total_debito,
        "total_credito": total_credito,
    }

    # Guardar en MySQL
    mov_id = guardar_movimiento(
        fecha_hora,
        cliente,
        empresa,
        banco,
        total_debito,
        total_credito,
        payload["lineas"],
    )

    # ✅ Mensaje limpio (DENTRO del if)
    st.success(f"Movimiento guardado correctamente ✅ (ID {mov_id})")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ID", mov_id)
    c2.metric("Líneas", len(lineas))
    c3.metric("Total Débito", f"{total_debito:,.2f}")
    c4.metric("Total Crédito", f"{total_credito:,.2f}")

    # Debug opcional
    with st.expander("Ver datos técnicos (debug)"):
        st.json({**payload, "id": mov_id})

    # 🔄 Reset del formulario
    st.session_state.lineas = pd.DataFrame([{
        "Cuenta": "",
        "Descripción": "",
        "Débito": 0.0,
        "Crédito": 0.0,
        "Notas": ""
    }])

    # Limpia uploads
    for i in range(len(uploaded_files)):
        key = f"file_{i}"
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()


# ----- Consulta -----
st.divider()
st.subheader("Consulta")

f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
with f1:
    desde = st.date_input("Desde esta fecha")
with f2:
    hasta = st.date_input("Hasta esta fecha")
with f3:
    filtro = st.selectbox("Filtro", ["Día", "Mes", "Año"])
with f4:
    st.write("")
    consultar = st.button("Consultar")

if consultar:
    rows = listar_movimientos(desde, hasta)
    demo = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["id", "Fecha", "Cliente", "Empresa", "Banco", "Débito", "Crédito", "Estado"]
    )
else:
    demo = pd.DataFrame(columns=["id", "Fecha", "Cliente", "Empresa", "Banco", "Débito", "Crédito", "Estado"])

st.dataframe(demo, width="stretch")

# ----- Export Excel -----
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    demo.to_excel(writer, index=False, sheet_name="Movimientos")

st.download_button(
    label="Descargar Excel",
    data=buffer.getvalue(),
    file_name="movimientos.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
st.markdown("### Detalle del movimiento")

if not demo.empty:
    # Normaliza columna id (a veces viene como "id" o "Id")
    col_id = "id" if "id" in demo.columns else ("Id" if "Id" in demo.columns else None)

    if col_id:
        ids = demo[col_id].dropna().astype(int).tolist()
        mov_id_sel = st.selectbox("Selecciona un ID para ver detalle", ids)

        # Cabecera
        mov = obtener_movimiento(int(mov_id_sel))
        if mov:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ID", mov["id"])
            c2.metric("Cliente", mov["cliente"])
            c3.metric("Empresa", mov["empresa"])
            c4.metric("Banco", mov["banco"])

            c5, c6, _ = st.columns([2, 2, 4])
            c5.metric("Total Débito", f'{float(mov["total_debito"]):,.2f}')
            c6.metric("Total Crédito", f'{float(mov["total_credito"]):,.2f}')

            # Detalle líneas
            detalle = listar_detalle_movimiento(int(mov_id_sel))
            det_df = pd.DataFrame(detalle) if detalle else pd.DataFrame(
                columns=["Cuenta", "Descripción", "Débito", "Crédito", "Notas", "Archivo"]
            )

            st.dataframe(det_df, width="stretch")

            # Descarga de archivos por línea (si existen)
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
                                    key=f"dl_{mov_id_sel}_{idx}"
                                )
                        except Exception as e:
                            st.warning(f"No se pudo leer el archivo: {path}")
        else:
            st.info("No se encontró la cabecera del movimiento.")
    else:
        st.info("No encontré columna de ID en la tabla de consulta.")
else:
    st.info("No hay resultados para mostrar detalle. Usa 'Consultar' primero.")
