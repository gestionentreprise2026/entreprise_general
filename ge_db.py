import pymysql
from datetime import datetime

def get_connection():
    return pymysql.connect(
        host="127.0.0.1",
        user="root",
        password="",
        database="gestion_entreprise",
        port=3307,
        cursorclass=pymysql.cursors.DictCursor
    )

def guardar_movimiento(fecha_hora, cliente, empresa, banco, total_debito, total_credito, lineas):
    # Convierte "dd/mm/YYYY HH:MM:SS" -> "YYYY-mm-dd HH:MM:SS" (MySQL DATETIME)
    fecha_hora_sql = datetime.strptime(fecha_hora, "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO movimientos
                (fecha_hora, cliente, empresa, banco, total_debito, total_credito)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (fecha_hora_sql, cliente, empresa, banco, total_debito, total_credito)
            )
            movimiento_id = cursor.lastrowid

            for l in lineas:
                cursor.execute(
                    """
                    INSERT INTO movimiento_detalle
                    (movimiento_id, cuenta, descripcion, debito, credito, notas, archivo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        movimiento_id,
                        l.get("Cuenta", ""),
                        l.get("Descripción", ""),
                        float(l.get("Débito", 0) or 0),
                        float(l.get("Crédito", 0) or 0),
                        l.get("Notas", ""),
                        l.get("archivo")  # por ahora None (luego guardamos ruta real)
                    )
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
                SELECT id,
                       DATE(fecha_hora) AS Fecha,
                       cliente AS Cliente,
                       empresa AS Empresa,
                       banco AS Banco,
                       total_debito AS Débito,
                       total_credito AS Crédito,
                       'OK' AS Estado
                FROM movimientos
                WHERE DATE(fecha_hora) BETWEEN %s AND %s
                ORDER BY id DESC
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
                SELECT id, fecha_hora, cliente, empresa, banco, total_debito, total_credito, creado_en
                FROM movimientos
                WHERE id = %s
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
