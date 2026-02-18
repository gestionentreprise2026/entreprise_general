import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
from io import BytesIO

from utils import apply_base_ui
from auth import require_login, sidebar_session

from ge_db import (
    guardar_movimiento,
    listar_movimientos,
    obtener_movimiento,
    listar_detalle_movimiento,
    listar_clientes,
    listar_empresas,
    listar_bancos,
)

# =========================
# 1) Config + Auth primero
# =========================
st.set_page_config(page_title="Movimientos", layout="wide")
require_login()

apply_base_ui(hide_nav=False)
sidebar_session()

user = st.session_state.auth or {}
rol = user.get("rol", "CONSULTA")

if rol not in ["ADMIN", "ASISTENTE", "SOCIO"]:
    st.error("⛔ No tienes permisos para acceder a Movimientos.")
    st.stop()

# =========================
# 2) Helpers
# =========================
def safe_filename(name: str) -> str:
    name = (name or "").strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name or "archivo"

@st.cache_data(ttl=60)
def load_catalogos():
    clientes = listar_clientes()
    empresas = listar_empresas()
    bancos = listar_bancos()
    return clientes, empresas, bancos

def validar_lineas(df: pd.DataFrame):
    """
    Reglas:
    - Cuenta obligatoria
    - No puede Débito y Crédito > 0 en la misma línea
    - No puede ambos 0
    - No negativos
    Retorna: (errores:list[str], total_debito, total_credito, diff)
    """
    errores = []
    if df is None or df.empty:
        return ["Debe existir al menos 1 línea."], 0.0, 0.0, 0.0

    x = df.copy()

    # Normaliza columnas (por si vienen NaN)
    for col in ["Cuenta", "Descripción", "Notas"]:
        if col in x.columns:
            x[col] = x[col].fillna("").astype(str)
    for col in ["Débito", "Crédito"]:
        if col in x.columns:
            x[col] = pd.to_numeric(x[col], errors="coerce").fillna(0.0)

    for i, row in x.iterrows():
        cuenta = str(row.get("Cuenta", "")).strip()
        d = float(row.get("Débito", 0.0))
        c = float(row.get("Crédito", 0.0))

        if cuenta == "":
            errores.append(f"Línea {i+1}: falta Cuenta.")
        if d < 0 or c < 0:
            errores.append(f"Línea {i+1}: no se permiten valores negativos.")
        if d > 0 and c > 0:
            errores.append(f"Línea {i+1}: no puede tener Débito y Crédito a la vez.")
        if d == 0 and c == 0:
            errores.append(f"Línea {i+1}: debe tener Débito o Crédito > 0.")

    total_d = float(x["Débito"].sum()) if "Débito" in x.columns else 0.0
    total_c = float(x["Crédito"].sum()) if "Crédito" in x.columns else 0.0
    diff = round(total_d - total_c, 2)

    return errores, total_d, total_c, diff

def fmt_money(v: float) -> str:
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"

# =========================
# 3) Topbar / Header
# =========================
st.markdown(
    """
    <style>
      .topbar {
        background:#0f172a;
        padding:12px 18px;
        border-radius:12px;
        color:white;
        font-weight:700;
        display:flex;
        justify-content:space-between;
        align-items:center;
      }
      .topbar small{opacity:.8;font-weight:600;}
    </style>
    <div class="topbar">
      <div>GESTION ENTERPRISE</div>
      <small>Movimientos</small>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")
st.title("Registro de Movimientos Varios")
st.caption("Movimientos / Registro de Movimientos Varios")

# =========================
# 4) Cargar catálogos
# =========================
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

# Por ahora fijo; luego traer de DB
cuentas = ["", "1010", "2020", "3030"]

# =========================
# 5) Tabs Pro
# =========================
tab_crear, tab_consultar, tab_detalle = st.tabs(["➕ Crear", "🔎 Consultar", "📄 Detalle"])

# =====================================================
# TAB 1: CREAR
# =====================================================
with tab_crear:
    # ---------- Cabecera ----------
    with st.container(border=True):
        st.subheader("Cabecera")

        colA, colB = st.columns([2, 3])

        with colA:
            if "mov_fecha_hora" not in st.session_state:
                st.session_state.mov_fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            fecha_hora = st.text_input("Fecha y Hora", key="mov_fecha_hora")

        with colB:
            c1, c2, c3 = st.columns(3)
            with c1:
                cliente_sel = st.selectbox("Cliente", clientes_opts, key="mov_cliente_sel")
            with c2:
                empresa_sel = st.selectbox("Empresa", empresas_opts, key="mov_empresa_sel")
            with c3:
                banco_sel = st.selectbox("Banco", bancos_opts, key="mov_banco_sel")

    # ✅ OJO: aquí ya salimos del container/columnas
    cliente_id = clientes_map.get(cliente_sel)
    empresa_id = empresas_map.get(empresa_sel)
    banco_id   = bancos_map.get(banco_sel)

    # ---------- Detalle (ancho completo) ----------
    st.write("")
    with st.container(border=True):
        st.subheader("Detalle")

        if "lineas" not in st.session_state:
            st.session_state.lineas = pd.DataFrame([{
                "Cuenta": "",
                "Descripción": "",
                "Débito": 0.0,
                "Crédito": 0.0,
                "Notas": ""
            }])

        b1, b2, b3, _ = st.columns([1.2, 1.2, 1.4, 6.2])
        with b1:
            if st.button("➕ Nueva", key="mov_nuevo_linea"):
                st.session_state.lineas = pd.concat(
                    [st.session_state.lineas,
                     pd.DataFrame([{"Cuenta": "", "Descripción": "", "Débito": 0.0, "Crédito": 0.0, "Notas": ""}])],
                    ignore_index=True
                )
        with b2:
            if st.button("📄 Duplicar", key="mov_dup_linea"):
                st.session_state.lineas = pd.concat(
                    [st.session_state.lineas, st.session_state.lineas.tail(1)],
                    ignore_index=True
                )
        with b3:
            if st.button("🧹 Limpiar", key="mov_limpiar"):
                st.session_state.lineas = pd.DataFrame([{
                    "Cuenta": "",
                    "Descripción": "",
                    "Débito": 0.0,
                    "Crédito": 0.0,
                    "Notas": ""
                }])
                # limpia uploaders previos
                for k in list(st.session_state.keys()):
                    if str(k).startswith("mov_file_"):
                        del st.session_state[k]
                st.rerun()

        edited = st.data_editor(
            st.session_state.lineas,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Cuenta": st.column_config.SelectboxColumn("Cuenta", options=cuentas, required=True),
                "Descripción": st.column_config.TextColumn("Descripción", help="Concepto de la línea"),
                "Débito": st.column_config.NumberColumn("Débito", min_value=0.0, step=0.01, format="%.2f"),
                "Crédito": st.column_config.NumberColumn("Crédito", min_value=0.0, step=0.01, format="%.2f"),
                "Notas": st.column_config.TextColumn("Notas"),
            },
            key="mov_editor",
        )
        st.session_state.lineas = edited

    # ---------- Archivos por línea ----------
    st.write("")
    with st.container(border=True):
        st.subheader("Archivos por línea")
        st.caption("Adjunta archivos (opcional) para cada línea del detalle.")

        uploaded_files = []
        for i in range(len(st.session_state.lineas)):
            f = st.file_uploader(f"Archivo línea {i+1}", key=f"mov_file_{i}")
            uploaded_files.append(f)

    # ---------- Validación + Resumen ----------
    errores_lineas, total_debito, total_credito, diff = validar_lineas(st.session_state.lineas)

    tiene_catalogos = (cliente_sel != "Seleccione" and empresa_sel != "Seleccione" and banco_sel != "Seleccione")
    balanceado = (diff == 0)
    puede_guardar = tiene_catalogos and balanceado and (len(errores_lineas) == 0)

    st.write("")
    with st.container(border=True):
        st.subheader("Resumen")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Líneas", len(st.session_state.lineas))
        m2.metric("Total Débito", fmt_money(total_debito))
        m3.metric("Total Crédito", fmt_money(total_credito))
        m4.metric("Diferencia", fmt_money(diff))

        if not tiene_catalogos:
            st.warning("Selecciona Cliente, Empresa y Banco para poder enviar.")
        if not balanceado and tiene_catalogos:
            st.error("El movimiento no está balanceado: Débito debe ser igual a Crédito.")

        if errores_lineas:
            with st.expander("Ver validaciones pendientes"):
                for e in errores_lineas[:50]:
                    st.write("•", e)

        confirmar = False
        if puede_guardar:
            confirmar = st.checkbox("Confirmo que los datos son correctos", key="mov_confirmar")

        # ---------- Guardar ----------
        st.write("")
        if st.button("✅ Enviar", type="primary", disabled=not (puede_guardar and confirmar), key="mov_enviar"):
            # Seguridad extra (por si cambió algo)
            if cliente_id is None or empresa_id is None or banco_id is None:
                st.error("No se pudieron resolver los IDs desde los catálogos.")
                st.stop()

            # Guardar archivos
            os.makedirs("data/uploads", exist_ok=True)

            lineas_df = st.session_state.lineas.copy()
            lineas_df["Cuenta"] = lineas_df["Cuenta"].fillna("").astype(str)

            lineas = lineas_df.to_dict(orient="records")

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
                float(total_debito),
                float(total_credito),
                lineas,
                cliente_id=cliente_id,
                empresa_id=empresa_id,
                banco_id=banco_id,
            )

            st.success(f"Movimiento guardado correctamente ✅ (ID {mov_id})")

            st.session_state.mov_fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ID", mov_id)
            c2.metric("Líneas", len(lineas))
            c3.metric("Total Débito", fmt_money(total_debito))
            c4.metric("Total Crédito", fmt_money(total_credito))

            with st.expander("Ver datos técnicos"):
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

            if "mov_confirmar" in st.session_state:
                del st.session_state["mov_confirmar"]

            st.rerun()

# =====================================================
# TAB 2: CONSULTAR
# =====================================================
with tab_consultar:
    st.subheader("Consulta")

    with st.container(border=True):
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

    st.dataframe(demo, use_container_width=True)

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

    st.info("Tip: Usa la pestaña 'Detalle' para seleccionar un ID y ver sus líneas/archivos.")

# =====================================================
# TAB 3: DETALLE
# =====================================================
with tab_detalle:
    st.subheader("Detalle del movimiento")

    # Cargar lista simple (últimos por rango, o default vacío)
    st.caption("Selecciona un ID (primero consulta en la pestaña 'Consultar' para ver resultados recientes).")

    # Opción: si ya consultaste antes, reutiliza demo del tab consultar no es directo en Streamlit.
    # Así que permitimos pedir IDs por fecha rápida aquí también:
    with st.container(border=True):
        d1, d2, d3 = st.columns([2, 2, 2])
        with d1:
            d_desde = st.date_input("Desde", key="mov_det_desde")
        with d2:
            d_hasta = st.date_input("Hasta", key="mov_det_hasta")
        with d3:
            st.write("")
            cargar_ids = st.button("Cargar IDs", key="mov_det_cargar_ids")

    ids = []
    if cargar_ids:
        rows = listar_movimientos(d_desde, d_hasta)
        df_ids = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not df_ids.empty:
            col_id = "id" if "id" in df_ids.columns else ("Id" if "Id" in df_ids.columns else None)
            if col_id:
                ids = df_ids[col_id].dropna().astype(int).tolist()

    if not ids:
        st.info("No hay IDs cargados. Usa el rango y presiona 'Cargar IDs'.")
    else:
        mov_id_sel = st.selectbox("Selecciona un ID", ids, key="mov_id_sel")

        mov = obtener_movimiento(int(mov_id_sel))
        if mov:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("ID", mov.get("id"))
                c2.metric("Cliente", mov.get("cliente", ""))
                c3.metric("Empresa", mov.get("empresa", ""))
                c4.metric("Banco", mov.get("banco", ""))

                c5, c6, _ = st.columns([2, 2, 4])
                c5.metric("Total Débito", fmt_money(mov.get("total_debito", 0)))
                c6.metric("Total Crédito", fmt_money(mov.get("total_credito", 0)))

            detalle = listar_detalle_movimiento(int(mov_id_sel))
            det_df = pd.DataFrame(detalle) if detalle else pd.DataFrame(
                columns=["Cuenta", "Descripción", "Débito", "Crédito", "Notas", "Archivo"]
            )

            st.dataframe(det_df, use_container_width=True)

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
                st.info("No hay archivos asociados.")
        else:
            st.warning("No se encontró la cabecera del movimiento.")
