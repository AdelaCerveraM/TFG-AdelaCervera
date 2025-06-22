import mysql.connector
from dotenv import load_dotenv

import os
import json
from datetime import datetime, timedelta
from pytz import timezone
import time 


# Carga de credenciales de conexión desde el archivo .env externo
dotenv_path = os.path.join(os.path.dirname(__file__), ".env.bbdd")
load_dotenv(dotenv_path=dotenv_path)

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}


# Funciones
def obtener_correos():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_correo, id_cliente, id_trabajo, remitente, destinatario,
               asunto, mensaje, fecha, tipo_mensaje, estado, mensaje_original_id, ruta_adjunto, generado_por_ia
        FROM correos
        ORDER BY fecha ASC
    """)
    correos = cursor.fetchall()
    cursor.close()
    conn.close()

    for correo in correos:
        correo["id"] = correo["id_correo"]
    return correos

def obtener_whatsapps():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_whatsapp, id_cliente, id_trabajo, remitente, destinatario, mensaje, fecha,
               tipo_mensaje, estado, mensaje_original_id, ruta_adjunto, generado_por_ia
        FROM whatsapps
        ORDER BY fecha ASC
    """)
    chats = cursor.fetchall()
    cursor.close()
    conn.close()

    zona_madrid = timezone("Europe/Madrid")
    for chat in chats:
        chat["id"] = chat["id_whatsapp"]
        if chat["fecha"] is not None:
            fecha = chat["fecha"]
            if fecha.tzinfo is None:
                fecha = zona_madrid.localize(fecha)
            chat["fecha"] = fecha.isoformat()

    return chats

def obtener_documentos(categoria, estado):
    tabla = "presupuestos" if categoria == "presupuestos" else "facturas"
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    if tabla == "presupuestos":
        cursor.execute("""
            SELECT p.id_cliente, p.id_trabajo, p.estado,
                   p.descripcion, p.conceptos, p.condiciones,
                   p.ruta_documento_word, p.ruta_documento_pdf,
                   p.fecha_creacion, p.fecha_modificacion,
                   p.canal, p.identificador_cliente,
                   c.nombre as nombre_cliente
            FROM presupuestos p
            JOIN clientes c ON p.id_cliente = c.id_cliente
            WHERE p.estado = %s
            ORDER BY p.fecha_creacion DESC
        """, (estado,))
    else:
        cursor.execute(f"""
            SELECT f.id_cliente, f.id_trabajo, f.estado,
                   f.descripcion, f.conceptos, f.informacion_adicional,
                   f.ruta_documento_word, f.ruta_documento_pdf,
                   f.fecha_creacion, f.fecha_modificacion,
                   f.canal, f.identificador_cliente,
                   c.nombre as nombre_cliente
            FROM {tabla} f
            JOIN clientes c ON f.id_cliente = c.id_cliente
            WHERE f.estado = %s
            ORDER BY f.fecha_creacion DESC
        """, (estado,))

    documentos = cursor.fetchall()
    cursor.close()
    conn.close()

    for doc in documentos:
        doc["categoria"] = categoria
        if isinstance(doc.get("conceptos"), str):
            try:
                doc["conceptos"] = json.loads(doc["conceptos"])
            except:
                doc["conceptos"] = []

    return documentos

def guardar_borrador_presupuesto(id_trabajo, descripcion, conceptos_json, condiciones):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE presupuestos
        SET descripcion = %s,
            conceptos = %s,
            condiciones = %s,
            fecha_modificacion = NOW()
        WHERE id_trabajo = %s
    """, (descripcion, conceptos_json, condiciones, id_trabajo))
    conn.commit()
    cursor.close()
    conn.close()

def guardar_borrador_factura(id_trabajo, descripcion, conceptos_json, informacion_adicional):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE facturas
        SET descripcion = %s,
            conceptos = %s,
            informacion_adicional = %s,
            fecha_modificacion = NOW()
        WHERE id_trabajo = %s
    """, (descripcion, conceptos_json, informacion_adicional, id_trabajo))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_factura_por_id_trabajo(id_trabajo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM facturas WHERE id_trabajo = %s", (id_trabajo,))
    factura = cursor.fetchone()
    cursor.close()
    conn.close()
    return factura

def marcar_factura_como_revisada(id_trabajo, nueva_ruta_pdf):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE facturas
        SET estado = 'revisado',
            fecha_modificacion = NOW(),
            ruta_documento_pdf = %s,
            ruta_documento_word = NULL
        WHERE id_trabajo = %s
    """, (nueva_ruta_pdf, id_trabajo))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_cliente_por_id(id_cliente):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clientes WHERE id_cliente = %s", (id_cliente,))
    cliente = cursor.fetchone()
    cursor.close()
    conn.close()
    return cliente

def obtener_horarios(fecha):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_horario, id_cliente, fecha, hora, duracion, descripcion, estado,
        direccion, poblacion, cp, provincia
        FROM horarios
        WHERE fecha = %s AND estado IN ('confirmado', 'ocupado')
        ORDER BY hora ASC
    """, (fecha,))
    resultados = cursor.fetchall()
    conn.close()

    for item in resultados:
        if isinstance(item.get("hora"), timedelta):
            total_minutes = item["hora"].total_seconds() / 60
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)
            item["hora"] = f"{hours:02d}:{minutes:02d}"
        elif isinstance(item.get("hora"), time):
            item["hora"] = item["hora"].strftime("%H:%M")

        id_cliente = item.get("id_cliente")
        if isinstance(id_cliente, int) and id_cliente > 0:
            cliente = obtener_cliente_por_id(id_cliente)
            item["nombre"] = cliente["nombre"] if cliente else ""
        else:
            item["nombre"] = ""

    return resultados

def borrar_horario(id_horario):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM horarios WHERE id_horario = %s", (id_horario,))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        cursor.close()
        conn.close()

def obtener_correos_pendientes():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_correo, mensaje, remitente
        FROM correos
        WHERE tipo_mensaje = 'entrante' AND estado = 'pendiente' AND mensaje IS NOT NULL
    """)
    pendientes = cursor.fetchall()
    cursor.close()
    conn.close()
    return pendientes

def obtener_whatsapps_pendientes():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_whatsapp, mensaje, remitente
        FROM whatsapps
        WHERE tipo_mensaje = 'entrante' AND estado = 'pendiente' AND mensaje IS NOT NULL
    """)
    pendientes = cursor.fetchall()
    cursor.close()
    conn.close()
    return pendientes

def marcar_correo_como_contestado(id_correo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE correos
        SET estado = 'contestado'
        WHERE id_correo = %s
    """, (id_correo,))
    conn.commit()
    cursor.close()
    conn.close()

def marcar_whatsapp_como_contestado(id_whatsapp):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute( """
        UPDATE whatsapps
        SET estado = 'contestado'
        WHERE id_whatsapp = %s
    """, (id_whatsapp,))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_respuestas_procesadas():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_correo, respuesta_ia
        FROM correos
        WHERE estado = 'procesado' AND respuesta_ia IS NOT NULL
    """)
    respuestas = cursor.fetchall()
    cursor.close()
    conn.close()
    return respuestas

def obtener_respuesta_saliente_asociada(id_original, canal):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    tabla = 'correos' if canal == 'correo' else 'whatsapps'

    cursor.execute(f"""
        SELECT * FROM {tabla}
        WHERE mensaje_original_id = %s AND tipo_mensaje = 'saliente'
        ORDER BY fecha DESC
        LIMIT 1
    """, (id_original,))
    correo = cursor.fetchone()
    cursor.close()
    conn.close()
    return correo

def insertar_respuesta_automatica_correos(mensaje_original, respuesta_ia):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO correos (
            id_cliente,
            id_trabajo,
            fecha,
            remitente,
            destinatario,
            asunto,
            mensaje,
            tipo_mensaje,
            estado,
            mensaje_original_id
        )
        VALUES (%s, %s, NOW(), %s, %s, %s, %s, 'saliente', 'procesado', %s)
    """, (
        mensaje_original["id_cliente"],
        mensaje_original["id_trabajo"],
        os.getenv("EMAIL"),                     
        mensaje_original["remitente"],           
        f"RE: {mensaje_original['asunto']}",
        respuesta_ia,
        mensaje_original["id_correo"]
    ))

    conn.commit()
    cursor.close()
    conn.close()

def insertar_respuesta_automatica_whatsapps(mensaje_original, respuesta_ia):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO whatsapps (
            id_cliente,
            id_trabajo,
            fecha,
            remitente,
            destinatario,
            mensaje,
            tipo_mensaje,
            estado,
            mensaje_original_id
        )
        VALUES (%s, %s, NOW(), %s, %s, %s, 'saliente', 'procesado', %s)
    """, (
        mensaje_original["id_cliente"],
        mensaje_original["id_trabajo"],
        "Empresa Demo",
        mensaje_original["remitente"],
        respuesta_ia,
        mensaje_original["id_whatsapp"]
    ))

    conn.commit()
    cursor.close()
    conn.close()

def actualizar_respuesta_y_marcar_enviada_correos(id_correo, mensaje):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE correos
        SET mensaje = %s, estado = 'enviado'
        WHERE id_correo = %s AND tipo_mensaje = 'saliente'
    """, (mensaje, id_correo))
    conn.commit()
    cursor.close()
    conn.close()

def actualizar_respuesta_y_marcar_enviada_whatsapps(id_whatsapp, mensaje):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE whatsapps
        SET mensaje = %s, estado = 'enviado'
        WHERE id_whatsapp = %s AND tipo_mensaje = 'saliente'
    """, (mensaje, id_whatsapp))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_datos_correo_por_id(id_correo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM correos WHERE id_correo = %s
    """, (id_correo,))
    correo = cursor.fetchone()
    cursor.close()
    conn.close()
    return correo

def obtener_datos_whatsapp_por_id(id_whatsapp):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT *
        FROM whatsapps
        WHERE id_whatsapp = %s
    """, (id_whatsapp,))
    whatsapp = cursor.fetchone()
    cursor.close()
    conn.close()
    return whatsapp

def marcar_mensaje_como_enviado(id_correo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE correos
        SET estado = 'enviado'
        WHERE id_correo = %s
    """, (id_correo,))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_ruta_pdf_por_id_trabajo(id_trabajo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ruta_documento_pdf FROM presupuestos WHERE id_trabajo = %s
    """, (id_trabajo,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    return resultado[0] if resultado else None

def actualizar_ruta_pdf(id_trabajo, ruta_pdf):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE presupuestos
        SET ruta_documento_pdf = %s
        WHERE id_trabajo = %s AND (ruta_documento_pdf IS NULL OR ruta_documento_pdf = '')
    """, (ruta_pdf, id_trabajo))
    conn.commit()
    cursor.close()
    conn.close()

def actualizar_fecha_modificacion(id_trabajo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE presupuestos
        SET fecha_modificacion = NOW()
        WHERE id_trabajo = %s
    """, (id_trabajo,))
    conn.commit()
    cursor.close()
    conn.close()

def generar_nuevo_id_trabajo():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id_trabajo) FROM presupuestos")
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    max_id = resultado[0] or 0
    return max_id + 1

def insertar_presupuesto(id_cliente, id_trabajo, descripcion, conceptos, condiciones, ruta_docx, ruta_pdf, canal=None, identificador_cliente=None, estado="pendiente"):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO presupuestos (
            id_cliente, id_trabajo, estado, descripcion, conceptos, condiciones,
            ruta_documento_word, ruta_documento_pdf, fecha_creacion, fecha_modificacion,
            canal, identificador_cliente
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
    """, (
        id_cliente,
        id_trabajo,
        estado,
        descripcion,
        json.dumps(conceptos, ensure_ascii=False),
        json.dumps(condiciones, ensure_ascii=False),
        ruta_docx,
        ruta_pdf,
        canal,
        identificador_cliente
    ))

    conn.commit()
    cursor.close()
    conn.close()

def insertar_mensaje_whatsapp_generado(destinatario, mensaje, id_original=None, ruta_adjunto=None):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    if id_original is not None:
        cursor.execute("""
            INSERT INTO whatsapps (
                remitente, destinatario, mensaje, fecha,
                tipo_mensaje, estado, mensaje_original_id, ruta_adjunto
            ) VALUES (%s, %s, %s, NOW(), 'saliente', 'enviado', %s, %s)
        """, (
            "Empresa Demo",
            destinatario,
            mensaje,
            id_original,
            ruta_adjunto
        ))
    else:
        cursor.execute("""
            INSERT INTO whatsapps (
                remitente, destinatario, mensaje, fecha,
                tipo_mensaje, estado, ruta_adjunto
            ) VALUES (%s, %s, %s, NOW(), 'saliente', 'enviado', %s)
        """, (
            "Empresa Demo",
            destinatario,
            mensaje,
            ruta_adjunto
        ))

    conn.commit()
    cursor.close()
    conn.close()

def insertar_mensaje_correo_generado(destinatario, asunto, mensaje, id_original=None, ruta_adjunto=None):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    if id_original is not None:
        cursor.execute("""
            INSERT INTO correos (
                remitente, destinatario, asunto, mensaje, fecha,
                tipo_mensaje, estado, mensaje_original_id, ruta_adjunto
            ) VALUES (%s, %s, %s, %s, NOW(), 'saliente', 'procesado', %s, %s)
        """, (
            "empresa.demo.tfg@gmail.com",
            destinatario,
            asunto,
            mensaje,
            id_original,
            ruta_adjunto
        ))
    else:
        cursor.execute("""
            INSERT INTO correos (
                remitente, destinatario, asunto, mensaje, fecha,
                tipo_mensaje, estado, ruta_adjunto
            ) VALUES (%s, %s, %s, %s, NOW(), 'saliente', 'procesado', %s)
        """, (
            "empresa.demo.tfg@gmail.com",
            destinatario,
            asunto,
            mensaje,
            ruta_adjunto
        ))

    conn.commit()
    cursor.close()
    conn.close()

def buscar_cliente_por_remitente(remitente):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clientes WHERE nombre = %s", (remitente,))
    cliente = cursor.fetchone()
    cursor.close()
    conn.close()
    return cliente

def obtener_ultimo_id_cliente():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id_cliente) FROM clientes")
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    return resultado[0] if resultado[0] is not None else 0

def asociar_trabajo_a_cliente(id_cliente, id_trabajo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("SELECT trabajos_asociados FROM clientes WHERE id_cliente = %s", (id_cliente,))
    resultado = cursor.fetchone()

    trabajos_actuales = resultado[0] if resultado and resultado[0] else ""
    trabajos_nuevos = trabajos_actuales + "," + str(id_trabajo) if trabajos_actuales else str(id_trabajo)

    cursor.execute("UPDATE clientes SET trabajos_asociados = %s WHERE id_cliente = %s", (trabajos_nuevos, id_cliente))
    conn.commit()
    cursor.close()
    conn.close()

def crear_ficha_cliente(datos):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT MAX(id_cliente) AS max_id FROM clientes")
    max_id = cursor.fetchone()["max_id"] or 0
    nuevo_id = max_id + 1

    cursor.execute("""
        INSERT INTO clientes (
            id_cliente, nombre, telefono, dni, direccion, poblacion, provincia, cp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        nuevo_id,
        datos.get("nombre", ""),
        datos.get("telefono", ""),
        datos.get("dni", ""),
        datos.get("direccion", ""),
        datos.get("poblacion", ""),
        datos.get("provincia", ""),
        datos.get("cp", "")
    ))

    conn.commit()
    cursor.close()
    conn.close()
    return nuevo_id, True 

def marcar_esperando_datos_cliente_whatsapp(id_mensaje):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("UPDATE whatsapps SET esperando_datos_cliente = TRUE WHERE id_whatsapp = %s", (id_mensaje,))
    conn.commit()
    cursor.close()
    conn.close()

def marcar_esperando_datos_cliente_correo(id_mensaje):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("UPDATE correos SET esperando_datos_cliente = TRUE WHERE id_correo = %s", (id_mensaje,))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_mensaje_esperando_datos(remitente, canal):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    if canal == "whatsapp":
        cursor.execute("""
            SELECT * FROM whatsapps
            WHERE remitente = %s AND esperando_datos_cliente = TRUE
            ORDER BY fecha DESC LIMIT 1
        """, (remitente,))
    else:
        cursor.execute("""
            SELECT * FROM correos
            WHERE remitente = %s AND esperando_datos_cliente = TRUE
            ORDER BY fecha DESC LIMIT 1
        """, (remitente,))

    mensaje = cursor.fetchone()
    cursor.close()
    conn.close()
    return mensaje

def desmarcar_esperando_datos_cliente_whatsapp(id_mensaje):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("UPDATE whatsapps SET esperando_datos_cliente = FALSE WHERE id_whatsapp = %s", (id_mensaje,))
    conn.commit()
    cursor.close()
    conn.close()

def desmarcar_esperando_datos_cliente_correo(id_mensaje):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("UPDATE correos SET esperando_datos_cliente = FALSE WHERE id_correo = %s", (id_mensaje,))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_presupuestos_recientes_por_cliente(id_cliente):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT fecha_creacion
        FROM presupuestos
        WHERE id_cliente = %s
        ORDER BY fecha_creacion DESC
        LIMIT 1
    """, (id_cliente,))
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

def obtener_presupuesto_por_id_trabajo(id_trabajo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM presupuestos WHERE id_trabajo = %s", (id_trabajo,))
    presupuesto = cursor.fetchone()
    cursor.close()
    conn.close()
    return presupuesto

def marcar_presupuesto_como_revisado(id_trabajo, nueva_ruta_pdf):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE presupuestos
        SET estado = 'revisado',
            fecha_modificacion = NOW(),
            ruta_documento_pdf = %s,
            ruta_documento_word = NULL
        WHERE id_trabajo = %s
    """, (nueva_ruta_pdf, id_trabajo))
    conn.commit()
    cursor.close()
    conn.close()

def actualizar_texto_respuesta(id_respuesta, nuevo_texto, canal, generado_por_ia=True):
    tabla = 'correos' if canal == 'correo' else 'whatsapps'
    campo_id = 'id_correo' if canal == 'correo' else 'id_whatsapp'

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    query = f"UPDATE {tabla} SET mensaje = %s, generado_por_ia = %s WHERE {campo_id} = %s"
    cursor.execute(query, (nuevo_texto, generado_por_ia, id_respuesta))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_presupuestos_revisados_sin_factura(id_cliente):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*
        FROM presupuestos p
        WHERE p.id_cliente = %s
          AND p.estado = 'revisado'
          AND NOT EXISTS (
              SELECT 1 FROM facturas f
              WHERE f.id_trabajo = p.id_trabajo
          )
        ORDER BY p.fecha_creacion DESC
    """, (id_cliente,))
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

def obtener_presupuestos_firmados_sin_factura(id_cliente):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*
        FROM presupuestos p
        WHERE p.id_cliente = %s
          AND p.estado = 'firmado'
          AND NOT EXISTS (
              SELECT 1 FROM facturas f
              WHERE f.id_trabajo = p.id_trabajo
          )
        ORDER BY p.fecha_creacion DESC
    """, (id_cliente,))
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

def insertar_factura(id_cliente, id_trabajo, ruta_documento, ruta_word, estado, canal, identificador_cliente, descripcion, conceptos, informacion_adicional):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO facturas (
            id_cliente, id_trabajo, ruta_documento_pdf, ruta_documento_word,
            estado, canal, identificador_cliente, descripcion, conceptos, informacion_adicional
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        id_cliente, id_trabajo, ruta_documento, ruta_word,
        estado, canal, identificador_cliente, descripcion, json.dumps(conceptos, ensure_ascii=False), informacion_adicional
    ))

    conn.commit()
    cursor.close()
    conn.close()

def obtener_citas_pendientes():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT h.id_trabajo, h.id_cliente, h.fecha, h.hora, h.duracion, h.descripcion,
               c.nombre AS nombre_cliente
        FROM horarios h
        JOIN clientes c ON h.id_cliente = c.id_cliente
        WHERE h.estado = 'pendiente'
        ORDER BY h.fecha ASC, h.hora ASC
    """)
    citas = cursor.fetchall()
    cursor.close()
    conn.close()
    return citas

def obtener_presupuestos_aprobados():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.id_trabajo, p.id_cliente, p.descripcion, p.fecha_creacion,
               c.nombre AS nombre_cliente
        FROM presupuestos p
        JOIN clientes c ON p.id_cliente = c.id_cliente
        WHERE p.estado = 'aprobado'
        ORDER BY p.fecha_creacion DESC
    """)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

def obtener_presupuestos_firmados():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.id_trabajo, p.id_cliente, p.descripcion, p.fecha_creacion,
               p.canal, p.identificador_cliente,
               c.nombre AS nombre_cliente
        FROM presupuestos p
        JOIN clientes c ON p.id_cliente = c.id_cliente
        WHERE p.estado = 'firmado'
        ORDER BY p.fecha_creacion DESC
    """)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

def insertar_bloque_personal(fecha, hora, duracion, descripcion, direccion, poblacion, estado="ocupado", id_cliente=-1, id_trabajo=-1):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO horarios (
            id_cliente, id_trabajo, fecha, hora, duracion,
            direccion, poblacion, descripcion, estado, fecha_creacion, fecha_modificacion
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
        )
    """, (id_cliente, id_trabajo, fecha, hora, duracion, direccion, poblacion, descripcion, estado))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_horarios_semana(fecha_str, poblacion=None):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    try:
        fecha_inicio = datetime.strptime(fecha_str, "%Y-%m-%d")
        fechas_semana = [(fecha_inicio + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

        query = """
            SELECT *
            FROM horarios
            WHERE fecha IN (%s, %s, %s, %s, %s, %s, %s)
              AND estado IN ('confirmado', 'ocupado')
        """
        params = fechas_semana

        if poblacion:
            query += " AND poblacion = %s"
            params.append(poblacion)

        cursor.execute(query, params)
        resultados = cursor.fetchall()

        
        for r in resultados:
            if isinstance(r.get("duracion"), timedelta):
                r["duracion"] = int(r["duracion"].total_seconds() // 60)
            elif isinstance(r.get("duracion"), int):
                r["duracion"] = r["duracion"]

            if isinstance(r.get("hora"), timedelta):
                total_minutes = r["hora"].total_seconds() / 60
                hours = int(total_minutes // 60)
                minutes = int(total_minutes % 60)
                r["hora"] = f"{hours:02d}:{minutes:02d}"
            elif isinstance(r.get("hora"), time):
                r["hora"] = r["hora"].strftime("%H:%M")

        return resultados
    finally:
        cursor.close()
        conn.close()

def actualizar_ruta_adjunto(canal, id_original, ruta_relativa):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    if canal == "whatsapp":
        cursor.execute("UPDATE whatsapps SET ruta_adjunto = %s WHERE id_whatsapp = %s", (ruta_relativa, id_original))
    else:
        cursor.execute("UPDATE correos SET ruta_adjunto = %s WHERE id_correo = %s", (ruta_relativa, id_original))

    conn.commit()
    cursor.close()
    conn.close()

def guardar_estado_chat(remitente, canal, id_cliente, chat):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id_estado_conversacion FROM estado_conversaciones
        WHERE remitente = %s AND canal = %s
    """, (remitente, canal))
    resultado = cursor.fetchone()

    if resultado:
        cursor.execute("""
            UPDATE estado_conversaciones
            SET chat = %s, id_cliente = %s
            WHERE remitente = %s AND canal = %s
        """, (chat, id_cliente, remitente, canal))
    else:
        cursor.execute("""
            INSERT INTO estado_conversaciones (remitente, canal, id_cliente, chat)
            VALUES (%s, %s, %s, %s)
        """, (remitente, canal, id_cliente, chat))

    conn.commit()
    cursor.close()
    conn.close()

def obtener_estado_chat(remitente, canal):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT chat FROM estado_conversaciones
        WHERE remitente = %s AND canal = %s
    """, (remitente, canal))
    resultado = cursor.fetchone()

    cursor.close()
    conn.close()
    return resultado['chat'] if resultado else None

def obtener_estado_conversaciones():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT remitente, canal, chat
        FROM estado_conversaciones
    """)
    estados = cursor.fetchall()

    cursor.close()
    conn.close()

    return estados

def marcar_presupuesto_como_firmado(id_trabajo, nueva_ruta_pdf):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE presupuestos
        SET estado = 'firmado',
            fecha_modificacion = NOW(),
            ruta_documento_pdf = %s,
            ruta_documento_word = NULL
        WHERE id_trabajo = %s
    """, (nueva_ruta_pdf, id_trabajo))
    conn.commit()
    cursor.close()
    conn.close()

def actualizar_ruta_adjunto_whatsapp(id_whatsapp, nueva_ruta):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE whatsapps
        SET ruta_adjunto = %s
        WHERE id_whatsapp = %s
    """, (nueva_ruta, id_whatsapp))
    conn.commit()
    cursor.close()
    conn.close()

def actualizar_ruta_adjunto_correo(id_correo, nueva_ruta):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE correos
        SET ruta_adjunto = %s
        WHERE id_correo = %s
    """, (nueva_ruta, id_correo))
    conn.commit()
    cursor.close()
    conn.close()

def obtener_id_cliente_por_remitente(remitente, canal):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_cliente FROM estado_conversaciones
        WHERE remitente = %s AND canal = %s
    """, (remitente, canal))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    return resultado["id_cliente"] if resultado else None

def actualizar_estado_mensaje(id_mensaje, canal, nuevo_estado):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    if canal == "whatsapp":
        cursor.execute("UPDATE whatsapps SET estado = %s WHERE id_whatsapp = %s", (nuevo_estado, id_mensaje))
    else:
        cursor.execute("UPDATE correos SET estado = %s WHERE id_correo = %s", (nuevo_estado, id_mensaje))

    conn.commit()
    cursor.close()
    conn.close()

def actualizar_cliente(data):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE clientes
        SET nombre = %s,
            dni = %s,
            telefono = %s,
            correo = %s,
            direccion = %s,
            poblacion = %s,
            provincia = %s,
            cp = %s
        WHERE id_cliente = %s
    """, (
        data.get("nombre", ""),
        data.get("dni", ""),
        data.get("telefono", ""),
        data.get("correo", ""),
        data.get("direccion", ""),
        data.get("poblacion", ""),
        data.get("provincia", ""),
        data.get("cp", ""),
        data["id_cliente"]
    ))

    conn.commit()
    cursor.close()
    conn.close()

def actualizar_horario(id_horario, descripcion, poblacion, hora, fecha):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE horarios
            SET descripcion = %s, poblacion = %s, hora = %s, fecha = %s
            WHERE id_horario = %s
        """, (descripcion, poblacion, hora, fecha, id_horario))
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        cursor.close()
        conn.close()

def insertar_whatsapp_entrante(remitente, mensaje):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO whatsapps (
            remitente, destinatario, mensaje, fecha,
            tipo_mensaje, estado
        ) VALUES (%s, %s, %s, NOW(), 'entrante', 'pendiente')
    """, (remitente, "Empresa Demo", mensaje))
    conn.commit()
    cursor.close()
    conn.close()
    
def insertar_cita_en_horarios(id_cliente, id_trabajo, fecha, hora, duracion, descripcion="Cita confirmada"):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO horarios (
            id_cliente, id_trabajo, fecha, hora, duracion, descripcion, estado
        ) VALUES (%s, %s, %s, %s, %s, %s, 'confirmado')
    """, (id_cliente, id_trabajo, fecha, hora, duracion, descripcion))

    conn.commit()
    cursor.close()
    conn.close()

def actualizar_estado_conversacion_por_remitente(remitente, canal, nuevo_estado):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE estado_conversaciones
        SET esperando_datos = %s
        WHERE remitente = %s AND canal = %s
    """, (nuevo_estado, remitente, canal))
    conn.commit()
    cursor.close()
    conn.close()

def esta_esperando_datos(remitente, canal):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT esperando_datos
        FROM estado_conversaciones
        WHERE remitente = %s AND canal = %s
    """, (remitente, canal))

    remitente = cursor.fetchall()
    cursor.close()
    conn.close()

    return remitente

def desmarcar_esperando_datos(remitente, canal):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE estado_conversaciones
        SET esperando_datos = FALSE
        WHERE remitente = %s AND canal = %s
    """, (remitente, canal))
    conn.commit()
    cursor.close()
    conn.close()

def marcar_factura_como_pagada(id_trabajo):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE facturas
        SET estado = 'pagado',
            fecha_modificacion = NOW()
        WHERE id_trabajo = %s
    """, (id_trabajo,))
    conn.commit()
    cursor.close()
    conn.close()