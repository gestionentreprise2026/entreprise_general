import pymysql
import bcrypt
from datetime import datetime

def get_connection():
    return pymysql.connect(
        host="127.0.0.1",
        user="root",
        password="",
        database="gestion_entreprise",
        port=3307,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

def verificar_login(usuario, password):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.id,
                       u.usuario,
                       u.nombre,
                       u.password_hash,
                       u.activo,
                       r.nombre AS rol
                FROM usuarios u
                JOIN roles r ON u.rol_id = r.id
                WHERE u.usuario = %s
                LIMIT 1
            """, (usuario,))

            user = cursor.fetchone()

            if not user:
                return None

            if user["activo"] != 1:
                return None

            # Verificar contraseña bcrypt
            if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return {
                    "id": user["id"],
                    "usuario": user["usuario"],
                    "nombre": user["nombre"],
                    "rol": user["rol"]
                }

            return None
    finally:
        conn.close()


# -------- ROLES ----------
def listar_roles():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre FROM roles ORDER BY nombre")
            return cur.fetchall()
    finally:
        conn.close()

# -------- USUARIOS ----------
def listar_usuarios():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.username, u.nombre, u.activo, r.nombre AS rol
                FROM usuarios u
                JOIN roles r ON r.id = u.rol_id
                ORDER BY u.id DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

def crear_usuario(username, nombre, password_hash, rol_id, activo=1):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO usuarios (username, nombre, password_hash, rol_id, activo)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, nombre, password_hash, rol_id, activo))
        conn.commit()
        return True
    finally:
        conn.close()

def set_usuario_activo(user_id, activo: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (activo, user_id))
        conn.commit()
    finally:
        conn.close()

def reset_password(user_id, new_hash):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET password_hash=%s WHERE id=%s", (new_hash, user_id))
        conn.commit()
    finally:
        conn.close()

def guardar_movimiento(
    fecha_hora,
    cliente,
    empresa,
    banco,
    total_debito,
    total_credito,
    lineas,
    cliente_id=None,
    empresa_id=None,
    banco_id=None,
):

    fecha_hora_sql = datetime.strptime(
        fecha_hora, "%d/%m/%Y %H:%M:%S"
    ).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO movimientos
                (fecha_hora, total_debito, total_credito,
                 cliente_id, empresa_id, banco_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    fecha_hora_sql,
                    total_debito,
                    total_credito,
                    cliente_id,
                    empresa_id,
                    banco_id,
                ),
            )

            movimiento_id = cursor.lastrowid

            for l in lineas:
                cursor.execute(
                    """
                    INSERT INTO movimiento_detalle
                    (movimiento_id, cuenta, descripcion,
                     debito, credito, notas, archivo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        movimiento_id,
                        l.get("Cuenta", "") or "",
                        l.get("Descripción", "") or "",
                        float(l.get("Débito", 0) or 0),
                        float(l.get("Crédito", 0) or 0),
                        l.get("Notas", "") or "",
                        l.get("archivo"),
                    ),
                )

        conn.commit()
        return movimiento_id
    finally:
        conn.close()

def listar_movimientos(desde, hasta):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    m.id,
                    DATE(m.fecha_hora) AS Fecha,
                    c.nombre AS Cliente,
                    e.nombre AS Empresa,
                    b.nombre AS Banco,
                    m.total_debito AS Débito,
                    m.total_credito AS Crédito,
                    'OK' AS Estado
                FROM movimientos m
                LEFT JOIN clientes c ON c.id = m.cliente_id
                LEFT JOIN empresas e ON e.id = m.empresa_id
                LEFT JOIN bancos b ON b.id = m.banco_id
                WHERE DATE(m.fecha_hora) BETWEEN %s AND %s
                ORDER BY m.id DESC
                """,
                (str(desde), str(hasta))
            )
            return cursor.fetchall()
    finally:
        conn.close()


def obtener_movimiento(mov_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    m.id, m.fecha_hora, m.total_debito, m.total_credito, m.creado_en,
                    m.cliente_id, m.empresa_id, m.banco_id,
                    c.nombre AS cliente,
                    e.nombre AS empresa,
                    b.nombre AS banco
                FROM movimientos m
                LEFT JOIN clientes c ON c.id = m.cliente_id
                LEFT JOIN empresas e ON e.id = m.empresa_id
                LEFT JOIN bancos b ON b.id = m.banco_id
                WHERE m.id = %s
                """,
                (mov_id,)
            )
            return cursor.fetchone()
    finally:
        conn.close()

def listar_detalle_movimiento(mov_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cuenta AS Cuenta, descripcion AS Descripción, debito AS Débito,
                       credito AS Crédito, notas AS Notas, archivo AS Archivo
                FROM movimiento_detalle
                WHERE movimiento_id = %s
                ORDER BY id ASC
                """,
                (mov_id,)
            )
            return cursor.fetchall()
    finally:
        conn.close()

# ---- Catalogos ----
def listar_clientes():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM clientes ORDER BY nombre")
            return cursor.fetchall()
    finally:
        conn.close()

def listar_empresas():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM empresas ORDER BY nombre")
            return cursor.fetchall()
    finally:
        conn.close()

def listar_bancos():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM bancos ORDER BY nombre")
            return cursor.fetchall()
    finally:
        conn.close()
        
def debug_server_info():
    conn = pymysql.connect(
        host="127.0.0.1",
        user="root",
        password="",
        port=3307,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT @@port AS port, @@version AS version, @@datadir AS datadir")
            info = cur.fetchone()
            cur.execute("SHOW DATABASES")
            dbs = cur.fetchall()
        return info, dbs
    finally:
        conn.close()
import bcrypt

def obtener_usuario_por_username(username: str):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.usuario, u.nombre, u.password_hash, u.activo,
                       r.nombre AS rol
                FROM usuarios u
                JOIN roles r ON r.id = u.rol_id
                WHERE u.usuario = %s
                LIMIT 1
                """,
                (username,),
            )
            return cursor.fetchone()
    finally:
        conn.close()

def verificar_login(username: str, password: str):
    user = obtener_usuario_por_username(username)
    if not user:
        return None
    if int(user["activo"]) != 1:
        return None

    stored = user["password_hash"].encode("utf-8")
    ok = bcrypt.checkpw(password.encode("utf-8"), stored)
    if not ok:
        return None

    # devolvemos solo lo necesario
    return {"id": user["id"], "usuario": user["usuario"], "nombre": user["nombre"], "rol": user["rol"]}

def crear_usuario(username: str, nombre: str, password: str, rol_id: int):
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO usuarios (usuario, nombre, password_hash, rol_id, activo)
                VALUES (%s, %s, %s, %s, 1)
                """,
                (username, nombre, pw_hash, rol_id),
            )
        conn.commit()
        return True
    finally:
        conn.close()
import bcrypt

def autenticar(username, password):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    u.id,
                    u.usuario,
                    u.password_hash,
                    u.rol_id,
                    r.nombre AS rol,
                    u.nombre
                FROM usuarios u
                JOIN roles r ON r.id = u.rol_id
                WHERE u.usuario = %s
                  AND u.activo = 1
                LIMIT 1
            """, (username,))

            user = cursor.fetchone()

            if not user:
                return None

            # 🔐 Verificar contraseña bcrypt
            if bcrypt.checkpw(
                password.encode("utf-8"),
                user["password_hash"].encode("utf-8")
            ):
                return {
                    "id": user["id"],
                    "usuario": user["usuario"],   # ✅ CORRECTO
                    "nombre": user.get("nombre"),
                    "rol": user["rol"],
                    "rol_id": user["rol_id"],
                }

            return None

    finally:
        conn.close()