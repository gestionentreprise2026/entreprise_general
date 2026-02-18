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
    listar_cuentas_activas,   # ✅ ahora sí lo usamos
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


def fmt_money(v: float) -> str:
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


@st.cache_data(ttl=60)
def load_catalogos():
    clientes = listar_clientes()
    empresas = listar_empresas()
    bancos = listar_bancos()
    return clientes, empresas, bancos


@st.cache_data(ttl=60)
def load_cuentas():
    return listar_cuentas_activas()


def naturaleza_desde_tipo(tipo: str) -> str:
    """
    Reglas:
    - EGRESO / GASTO => CREDITO
    - INGRESO => DEBITO
    """
    t = (tipo or "").strip().upper()

    if t in ["EGRESO", "GASTO"]:
        return "CREDITO"

    if t in ["INGRESO"]:
        return "DEBITO"

    # Default
    return "DEBITO"

def validar_lineas_monto(df: pd.DataFrame, cuentas_label_to_id: dict) -> list:
    errores = []
    if df is None or df.empty:
        return ["Debe existir al menos 1 línea."]

    x = df.copy()
    x["cuenta"] = x["cuenta"].fillna("Seleccione").astype(str)
    x["monto"] = pd.to_numeric(x["monto"], errors="coerce").fillna(0.0)

    for i, row in x.iterrows():
        cuenta_label = row.get("cuenta", "Seleccione")
        monto = float(row.get("monto", 0.0))

        if cuenta_label == "Seleccione" or cuenta_label not in cuentas_label_to_id:
            errores.append(f"Línea {i+1}: selecciona una cuenta válida.")
        if monto <= 0:
            errores.append(f"Línea {i+1}: el monto debe ser mayor a 0.")

    return errores


def construir_lineas_para_guardar(
    df: pd.DataFrame,
    cuentas_label_to_id: dict,
    cuentas_id_to_nat: dict
):
    x = df.copy()
    x["cuenta"] = x["cuenta"].fillna("Seleccione").astype(str)
    x["monto"] = pd.to_numeric(x["monto"], errors="coerce").fillna(0.0)

    lineas_out = []
    for _, r in x.iterrows():
        cuenta_label = r.get("cuenta", "Seleccione")
        cuenta_id = cuentas_label_to_id.get(cuenta_label)

        monto = float(r.get("monto", 0.0) or 0.0)
        nat = cuentas_id_to_nat.get(cuenta_id, "DEBITO")  # DEBITO/CREDITO

        deb = monto if nat == "DEBITO" else 0.0
        cre = monto if nat == "CREDITO" else 0.0

        lineas_out.append({
            "Cuenta": cuenta_id,                 # <- BD (movimiento_detalle.cuenta)
            "Descripción": r.get("descripcion", "") or "",
            "Débito": float(deb),
            "Crédito": float(cre),
            "Notas": r.get("notas", "") or "",
        })

    total_debito = float(sum(l["Débito"] for l in lineas_out))
    total_credito = float(sum(l["Crédito"] for l in lineas_out))
    diff = round(total_debito - total_credito, 2)

    return lineas_out, total_debito, total_credito, diff

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
# 4) Cargar catálogos + cuentas
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

# ---- Cuentas desde BD ----
try:
    cuentas_db = load_cuentas()
except Exception as e:
    st.error(f"No se pudo cargar cuentas desde la BD: {e}")
    cuentas_db = []

# Labels para selectbox
cuentas_label_to_id = {}
cuentas_id_to_nat = {}

for c in cuentas_db:
    cid = c.get("id_cue") or c.get("id") or c.get("id_cuenta")
    nombre = c.get("nombre_cue") or c.get("nombre") or str(cid)
    tipo = c.get("tipo_cue") or c.get("tipo") or ""
    nat = naturaleza_desde_tipo(tipo)

    label = f"{nombre} (ID {cid}) · {tipo}"
    cuentas_label_to_id[label] = cid
    cuentas_id_to_nat[cid] = nat

cuentas_opts = ["Seleccione"] + list(cuentas_label_to_id.keys())


# =========================
# 5) Tabs
# =========================
tab_crear, tab_consultar, tab_detalle = st.tabs(["➕ Crear", "🔎 Consultar", "📄 Detalle"])


# =====================================================
# TAB 1: CREAR
# =====================================================
def normalizar_lineas(df: pd.DataFrame) -> pd.DataFrame:
    """Asegura columnas/tipos estables para el editor."""
    if df is None or df.empty:
        df = pd.DataFrame([{"cuenta": "Seleccione", "descripcion": "", "monto": 0.0, "notas": ""}])

    df = df.copy()

    # Por si llegan columnas con otros nombres (mayúsculas o acentos)
    ren = {
        "Cuenta": "cuenta",
        "Descripción": "descripcion",
        "Descripcion": "descripcion",
        "Monto": "monto",
        "Notas": "notas",
    }
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})

    # Garantizar columnas
    defaults = {"cuenta": "Seleccione", "descripcion": "", "monto": 0.0, "notas": ""}
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Orden y solo columnas necesarias
    df = df[["cuenta", "descripcion", "monto", "notas"]]

    # Tipos
    df["cuenta"] = df["cuenta"].fillna("Seleccione").astype(str)
    df["descripcion"] = df["descripcion"].fillna("").astype(str)
    df["notas"] = df["notas"].fillna("").astype(str)
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0.0)

    return df


with tab_crear:
    # ---------- Cabecera ----------
    with st.container(border=True):
        st.subheader("Cabecera")

        colA, colB = st.columns([2, 3])

        with colA:
            # valor inicial UNA SOLA VEZ
            if "mov_fecha_hora" not in st.session_state:
                st.session_state["mov_fecha_hora"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            fecha_hora = st.text_input("Fecha y Hora", key="mov_fecha_hora")

        with colB:
            c1, c2, c3 = st.columns(3)
            with c1:
                cliente_sel = st.selectbox("Cliente", clientes_opts, key="mov_cliente_sel")
            with c2:
                empresa_sel = st.selectbox("Empresa", empresas_opts, key="mov_empresa_sel")
            with c3:
                banco_sel = st.selectbox("Banco", bancos_opts, key="mov_banco_sel")

    cliente_id = clientes_map.get(cliente_sel)
    empresa_id = empresas_map.get(empresa_sel)
    banco_id = bancos_map.get(banco_sel)

    # ---------- Detalle ----------
    st.write("")
    with st.container(border=True):
        st.subheader("Detalle")
        st.caption("Selecciona una cuenta y escribe el monto. El sistema decide Débito o Crédito según el tipo de cuenta.")

        # Inicializar una sola vez
        if "lineas" not in st.session_state:
            st.session_state["lineas"] = pd.DataFrame([{
                "cuenta": "Seleccione",
                "descripcion": "",
                "monto": 0.0,
                "notas": ""
            }])

        # Normalizar SIEMPRE antes del editor
        st.session_state["lineas"] = normalizar_lineas(st.session_state["lineas"])

        b1, b2, b3, _ = st.columns([1.2, 1.2, 1.4, 6.2])

        with b1:
            if st.button("➕ Nueva", key="mov_nuevo_linea"):
                st.session_state["lineas"] = pd.concat(
                    [st.session_state["lineas"],
                     pd.DataFrame([{"cuenta": "Seleccione", "descripcion": "", "monto": 0.0, "notas": ""}])],
                    ignore_index=True
                )
                st.session_state["lineas"] = normalizar_lineas(st.session_state["lineas"])

        with b2:
            if st.button("📄 Duplicar", key="mov_dup_linea"):
                st.session_state["lineas"] = pd.concat(
                    [st.session_state["lineas"], st.session_state["lineas"].tail(1)],
                    ignore_index=True
                )
                st.session_state["lineas"] = normalizar_lineas(st.session_state["lineas"])

        with b3:
            if st.button("🧹 Limpiar", key="mov_limpiar"):
                st.session_state["lineas"] = pd.DataFrame([{
                    "cuenta": "Seleccione",
                    "descripcion": "",
                    "monto": 0.0,
                    "notas": ""
                }])

                # borrar uploads
                for k in list(st.session_state.keys()):
                    if str(k).startswith("mov_file_"):
                        del st.session_state[k]

                # borrar confirmación
                if "mov_confirmar" in st.session_state:
                    del st.session_state["mov_confirmar"]

                st.rerun()

        # --- Editor (persistente) ---
        edited = st.data_editor(
            st.session_state["lineas"],
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "cuenta": st.column_config.SelectboxColumn("Cuenta", options=cuentas_opts, required=True),
                "descripcion": st.column_config.TextColumn("Descripción", help="Concepto de la línea"),
                "monto": st.column_config.NumberColumn("Monto", min_value=0.0, step=0.01, format="%.2f"),
                "notas": st.column_config.TextColumn("Notas"),
            },
            key="mov_editor",
        )

        # Guardar SIEMPRE lo que devuelve el editor
        if edited is None:
            edited = st.session_state["lineas"].copy()

        edited = edited.copy()

        # Asegurar columnas (por si algo cambia)
        defaults = {
            "cuenta": "Seleccione",
            "descripcion": "",
            "monto": 0.0,
            "notas": "",
        }
        for col, default in defaults.items():
            if col not in edited.columns:
                edited[col] = default

        # Asegurar tipos
        edited["cuenta"] = edited["cuenta"].fillna("Seleccione").astype(str)
        edited["descripcion"] = edited["descripcion"].fillna("").astype(str)
        edited["notas"] = edited["notas"].fillna("").astype(str)
        edited["monto"] = pd.to_numeric(edited["monto"], errors="coerce").fillna(0.0)

        # Persistir en session_state
        st.session_state["lineas"] = edited

        # Debug naturaleza
        prev = st.session_state["lineas"].copy()
        prev["Cuenta_id"] = prev["cuenta"].map(cuentas_label_to_id).fillna("")
        prev["Naturaleza"] = prev["Cuenta_id"].apply(lambda cid: cuentas_id_to_nat.get(cid, "") if cid != "" else "")
        with st.expander("Ver naturaleza por línea (debug)"):
            st.dataframe(prev[["cuenta", "Naturaleza", "monto", "descripcion", "notas"]], use_container_width=True)

    # ---------- Archivos por línea ----------
    st.write("")
    with st.container(border=True):
        st.subheader("Archivos por línea")
        st.caption("Adjunta archivos (opcional) para cada línea del detalle.")
        uploaded_files = []
        for i in range(len(st.session_state["lineas"])):
            f = st.file_uploader(f"Archivo línea {i+1}", key=f"mov_file_{i}")
            uploaded_files.append(f)

    # ---------- Validación + Construcción ----------
    errores_lineas = validar_lineas_monto(st.session_state["lineas"], cuentas_label_to_id)

    lineas_out, total_debito, total_credito, diff = construir_lineas_para_guardar(
        st.session_state["lineas"], cuentas_label_to_id, cuentas_id_to_nat
    )

    tiene_catalogos = (cliente_sel != "Seleccione" and empresa_sel != "Seleccione" and banco_sel != "Seleccione")
    balanceado = (diff == 0)

    # ✅ Para este módulo (solo EGRESO/GASTO): NO exigimos balance
    puede_guardar = tiene_catalogos and (len(errores_lineas) == 0)

    # ---------- Resumen ----------
    st.write("")
    with st.container(border=True):
        st.subheader("Resumen")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Líneas", len(st.session_state["lineas"]))
        m2.metric("Total Débito", fmt_money(total_debito))
        m3.metric("Total Crédito", fmt_money(total_credito))
        m4.metric("Diferencia", fmt_money(diff))

        if not tiene_catalogos:
            st.warning("Selecciona Cliente, Empresa y Banco para poder enviar.")

        if errores_lineas:
            with st.expander("Ver validaciones pendientes"):
                for e in errores_lineas[:50]:
                    st.write("•", e)

        # ⚠ SOLO MENSAJE INFORMATIVO (NO BLOQUEA)
        if tiene_catalogos and not balanceado:
            st.warning("Movimiento no balanceado (Egreso/Gasto). Se guardará igualmente.")

        confirmar = False
        if puede_guardar:
            confirmar = st.checkbox("Confirmo que los datos son correctos", key="mov_confirmar")

        st.write("")
        if st.button("✅ Enviar", type="primary", disabled=not (puede_guardar and confirmar), key="mov_enviar"):
            if cliente_id is None or empresa_id is None or banco_id is None:
                st.error("No se pudieron resolver los IDs desde los catálogos.")
                st.stop()

            os.makedirs("data/uploads", exist_ok=True)

            # Adjuntar paths a líneas
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

            for i in range(len(lineas_out)):
                lineas_out[i]["archivo"] = saved_paths[i] if i < len(saved_paths) else None

            mov_id = guardar_movimiento(
                fecha_hora,
                cliente_sel,
                empresa_sel,
                banco_sel,
                float(total_debito),
                float(total_credito),
                lineas_out,
                cliente_id=cliente_id,
                empresa_id=empresa_id,
                banco_id=banco_id,
            )

            st.success(f"Movimiento guardado correctamente ✅ (ID {mov_id})")

            # ✅ Reset completo
            st.session_state["lineas"] = pd.DataFrame([{
                "cuenta": "Seleccione",
                "descripcion": "",
                "monto": 0.0,
                "notas": ""
            }])

            # borrar uploads
            for i in range(len(uploaded_files)):
                k = f"mov_file_{i}"
                if k in st.session_state:
                    del st.session_state[k]

            # borrar confirmación
            if "mov_confirmar" in st.session_state:
                del st.session_state["mov_confirmar"]

            # reiniciar fecha/hora: borrar la key
            if "mov_fecha_hora" in st.session_state:
                del st.session_state["mov_fecha_hora"]

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
    st.caption("Selecciona un ID (primero consulta en la pestaña 'Consultar' para ver resultados recientes).")

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
                columns=["cuenta", "descripcion", "Débito", "Crédito", "notas", "Archivo"]
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


