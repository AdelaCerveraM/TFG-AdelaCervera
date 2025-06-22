# ------------------------------------ IMPORTACIONES NECESARIAS ------------------------------------

from flask import Flask, jsonify, request, send_file, render_template, redirect, url_for
import os
import webbrowser
import mimetypes
import threading
import time
import shutil

from Scripts.bbdd import *

from Scripts.generador_respuesta import generar_respuesta_automatica
from Scripts.volcado_correos import volcar_correos_no_leidos
from Scripts.generador_borrador_factura import generar_borrador_factura_automatico
from Scripts.generador_borrador_presupuesto import generar_borrador_presupuesto_automatico, completar_ficha_cliente
from Scripts.generador_presupuesto import generar_presupuesto, ConfiguracionPresupuesto
from Scripts.generador_factura import generar_factura, ConfiguracionFactura
from Scripts.procesador_firmas import procesar_archivo_firmado
from Scripts.envio_respuesta_aprobada import enviar_respuesta_por_correo, enviar_respuesta_por_whatsapp


# -------------------------------------- CONFIGURACIÓN FLASK ---------------------------------------

app = Flask(__name__, static_folder='Web', template_folder='Web')


# --------------------------------------- RUTAS PRINCIPALES ----------------------------------------

# Redirige '/' a la página principal
@app.route('/')
def home():
    return redirect(url_for('index'))

# Página principal
@app.route('/index.html')
def index():
    return render_template('index.html')

# Página de documentación
@app.route('/documentacion.html')
def documentacion():
    return render_template('documentacion.html')

# Página de chat
@app.route('/chat.html')
def chat():
    return render_template('chat.html')

# Página de calendario
@app.route('/calendario.html')
def calendario():
    return render_template('calendario.html')

# Página de citas
@app.route('/citas.html')
def citas():
    return render_template('citas.html')


# ----------------------------- RUTAS PARA ARCHIVOS ESTÁTICOS (CSS e imágenes) -----------------------------

# Hoja de estilos general
@app.route('/estilos.css')
def estilos():
    return send_file('Web/estilos.css', mimetype='text/css')

# Hoja de estilos index
@app.route('/estilos_index.css')
def estilos_index():
    return send_file('Web/estilos_index.css', mimetype='text/css')

# Estilos específicos de documentación
@app.route('/estilos_documentacion.css')
def estilos_documentacion():
    return send_file('Web/estilos_documentacion.css', mimetype='text/css')

# Estilos específicos de chat
@app.route('/estilos_chat.css')
def estilos_chat():
    return send_file('Web/estilos_chat.css', mimetype='text/css')

# Estilos específicos de calendario
@app.route('/estilos_calendario.css')
def estilos_calendario():
    return send_file('Web/estilos_calendario.css', mimetype='text/css')

# Estilos específicos de calendario
@app.route('/estilos_citas.css')
def estilos_citas():
    return send_file('Web/estilos_citas.css', mimetype='text/css')

# Archivos de imagen (protección básica incluida)
@app.route('/Imagenes/<path:filename>')
def imagenes(filename):
    if '..' in filename or filename.startswith('/'):
        return "Ruta no válida", 400
    full_path = os.path.join('Web/Imagenes', filename)
    if not os.path.exists(full_path):
        return "Imagen no encontrada", 404
    ext = os.path.splitext(filename)[1].lower()
    mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png' if ext == '.png' else 'image/gif'
    return send_file(full_path, mimetype=mime_type)


# ------------------------------------- EXTENSIÓN DE TIPOS MIME --------------------------------------

# Soporte para archivos .docx
mimetypes.add_type('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx')


# -------------------------------------- RUTAS CON BBDD Y SCRIPTS BACKEND ---------------------------------------

# Obtener correos desde la base de datos
@app.route('/api/correos')
def api_correos():
    return jsonify(obtener_correos())

# Obtener mensajes de WhatsApp desde la base de datos
@app.route('/api/whatsapps')
def api_whatsapps():
    return jsonify(obtener_whatsapps())

# Obtener documentos filtrados por categoría y estado
@app.route('/api/documentos')
def api_documentos():
    categoria = request.args.get('categoria')
    estado = request.args.get('estado')

    if not categoria or not estado:
        return jsonify({"error": "Faltan parámetros"}), 400

    documentos = obtener_documentos(categoria, estado)
    return jsonify(documentos)

# Obtener todos los documentos de una categoría, agrupando por estado
@app.route('/api/documentos_totales')
def api_obtener_documentos_totales():
    categoria = request.args.get("categoria")
    documentos = []
    for estado in ["pendiente", "revisado", "firmado"]:
        documentos += obtener_documentos(categoria, estado)
    return jsonify(documentos)

# Obtener datos de un cliente concreto por su ID
@app.route('/api/clientes/<int:id_cliente>')
def api_datos_cliente(id_cliente):
    cliente = obtener_cliente_por_id(id_cliente)
    if cliente:
        return jsonify(cliente)
    return jsonify({"error": "Cliente no encontrado"}), 404

# Obtener horarios programados para una fecha concreta
@app.route('/api/horarios')
def api_horarios():
    fecha = request.args.get('fecha')
    if not fecha:
        return jsonify({"error": "Falta parámetro 'fecha'"}), 400
    return jsonify(obtener_horarios(fecha))

# Obtener documento desde ruta relativa al directorio Scripts
@app.route('/api/view-document')
def view_document():
    file = request.args.get('file')
    if not file:
        return "Falta parámetro 'file'", 400

    ruta_absoluta = os.path.abspath(os.path.join(os.path.dirname(__file__), "Scripts", file.replace("\\", "/")))

    if not os.path.isfile(ruta_absoluta):
        return f"Archivo no encontrado: {ruta_absoluta}", 404

    return send_file(ruta_absoluta)

# Obtener respuestas automáticas ya procesadas
@app.route('/api/respuestas_procesadas')
def api_respuestas_procesadas():
    return jsonify(obtener_respuestas_procesadas())

# Marcar como enviado un mensaje y su original como contestado
@app.route('/api/enviar_respuesta', methods=['POST'])
def api_enviar_respuesta():
    id_respuesta = request.form.get('id_respuesta')
    id_original = request.form.get('id_original')

    if not id_respuesta or not id_original:
        return jsonify({"error": "Faltan parámetros"}), 400

    marcar_mensaje_como_enviado(id_respuesta)
    marcar_correo_como_contestado(id_original)

    return jsonify({"ok": True})

# Obtener citas en estado pendiente
@app.route('/api/citas_pendientes')
def api_citas_pendientes():
    return jsonify(obtener_citas_pendientes())

# Obtener presupuestos firmados listos para generar factura
@app.route('/api/presupuestos_firmados')
def api_presupuestos_firmados():
    return jsonify(obtener_presupuestos_firmados())

# Insertar nuevo mensaje de WhatsApp entrante
@app.route('/api/insertar_whatsapp', methods=['POST'])
def api_insertar_whatsapp():
    data = request.get_json()
    remitente = data.get("remitente")
    mensaje = data.get("mensaje")

    if not remitente or not mensaje:
        return jsonify({"error": "Faltan datos"}), 400

    insertar_whatsapp_entrante(remitente, mensaje)
    return jsonify({"ok": True})

# Obtener horarios confirmados u ocupados para una semana
@app.route('/api/horarios_semana')
def api_horarios_semana():
    fecha = request.args.get("fecha")
    if not fecha:
        return jsonify({"error": "Falta el parámetro 'fecha'"}), 400

    horarios = obtener_horarios_semana(fecha)
    return jsonify(horarios)

# Actualizar los datos de un horario existente
@app.route("/api/actualizar_horario", methods=["POST"])
def api_actualizar_horario():
    datos = request.json
    actualizado = actualizar_horario(
        datos["id"], datos["descripcion"], datos["poblacion"], datos["hora"], datos["fecha"]
    )
    return jsonify({"ok": actualizado})

# Borrar un bloque de horario a partir de su ID
@app.route('/api/borrar_horario', methods=['POST'])
def api_borrar_horario():
    datos = request.get_json()
    id_horario = datos.get("id")
    if not id_horario:
        return jsonify({"error": "Falta id"}), 400
    borrado = borrar_horario(id_horario)
    return jsonify({"ok": borrado})

# Genera un nuevo presupuesto a partir de un pedido recibido
@app.route('/api/generar_presupuesto', methods=['POST'])
def api_generar_presupuesto():
    pedido = request.get_json()
    if not pedido:
        return jsonify({"error": "Falta contenido JSON"}), 400

    id_trabajo = pedido.get("id_trabajo")
    if id_trabajo is None:
        return jsonify({"error": "Falta id_trabajo"}), 400

    config = ConfiguracionPresupuesto()
    ruta_docx, ruta_pdf, id_trabajo = generar_presupuesto(pedido, config, id_trabajo)

    # Guardar ruta_pdf en BBDD solo si no existe
    ruta_pdf_en_bd = obtener_ruta_pdf_por_id_trabajo(id_trabajo)  
    if not ruta_pdf_en_bd and ruta_pdf:
        actualizar_ruta_pdf(id_trabajo, ruta_pdf)

    # Actualizar fecha_modificacion siempre que generes un presupuesto
    actualizar_fecha_modificacion(id_trabajo)

    return jsonify({
        "ruta_word": ruta_docx,
        "ruta_pdf": ruta_pdf,
        "id_trabajo": id_trabajo
    })

# Guarda un borrador de presupuesto con los datos editados por el usuario
@app.route('/api/guardar_borrador_presupuesto', methods=['POST'])
def api_guardar_borrador_presupuesto():
    data = request.get_json()
    id_trabajo = data.get("id_trabajo")
    descripcion = data.get("descripcion", "")
    conceptos = data.get("conceptos", [])
    condiciones = data.get("condiciones", "")

    if not id_trabajo:
        return jsonify({"error": "Falta id_trabajo"}), 400

    import json
    conceptos_json = json.dumps(conceptos, ensure_ascii=False)

    guardar_borrador_presupuesto(id_trabajo, descripcion, conceptos_json, condiciones)

    return jsonify({"ok": True})

# Guarda un borrador de factura generado o editado manualmente
@app.route('/api/guardar_borrador_factura', methods=['POST'])
def api_guardar_borrador_factura():
    data = request.get_json()
    id_trabajo = data.get("id_trabajo")
    descripcion = data.get("descripcion", "")
    conceptos = data.get("conceptos", [])
    info_adicional = data.get("informacion_adicional", "")

    if not id_trabajo:
        return jsonify({"error": "Falta id_trabajo"}), 400

    import json
    conceptos_json = json.dumps(conceptos, ensure_ascii=False)

    guardar_borrador_factura(id_trabajo, descripcion, conceptos_json, info_adicional)

    return jsonify({"ok": True})

# Busca huecos disponibles para agendar una cita con la duración deseada
@app.route("/api/buscar_huecos")
def api_buscar_huecos():
    id_trabajo = request.args.get("id_trabajo", type=int)
    duracion = request.args.get("duracion", type=int)

    if not id_trabajo or not duracion:
        return jsonify([])

    from Scripts.horarios import buscar_huecos_disponibles
    huecos = buscar_huecos_disponibles(id_trabajo, duracion)

    return jsonify(huecos)

# Procesa una respuesta final redactada por el usuario y la envía al cliente por el canal correspondiente
@app.route('/enviar_respuesta_final', methods=['POST'])
def enviar_respuesta_final():
    canal = request.form.get('canal')
    id_original = request.form.get('id_correo' if canal == 'correo' else 'id_whatsapp')
    respuesta = request.form.get('respuesta_final')
    destinatario = request.form.get('destinatario')

    if not respuesta or not destinatario:
        return jsonify({"error": "Faltan destinatario o respuesta"}), 400

    if canal == 'correo':
        correos = obtener_correos()
        mensaje_original = next((c for c in correos if str(c.get('id')) == str(id_original)), None)

        if mensaje_original:
            asunto_original = mensaje_original.get('asunto') or 'Sin asunto'
            nuevo_asunto = f"RE: {asunto_original}"

            insertar_mensaje_correo_generado(
                destinatario=mensaje_original['remitente'],
                asunto=nuevo_asunto,
                mensaje=respuesta,
                ruta_adjunto=None
            )
        else:
            insertar_mensaje_correo_generado(
                destinatario=destinatario,
                asunto="(sin asunto)",
                mensaje=respuesta,
                ruta_adjunto=None
            )

    elif canal == 'whatsapp':
        whatsapps = obtener_whatsapps()
        mensaje_original = next((w for w in whatsapps if str(w.get('id')) == str(id_original)), None)

        if mensaje_original:
            insertar_mensaje_whatsapp_generado(
                destinatario=mensaje_original['remitente'],
                mensaje=respuesta,
                ruta_adjunto=None
            )
        else:
            insertar_mensaje_whatsapp_generado(
                destinatario=destinatario,
                mensaje=respuesta,
                ruta_adjunto=None
            )

    else:
        return jsonify({"error": "Canal no reconocido"}), 400
    
    # Enviar la respuesta efectivamente por el canal correspondiente
    if canal == 'correo':
        asunto = nuevo_asunto if 'nuevo_asunto' in locals() else "(sin asunto)"
        enviar_respuesta_por_correo(destinatario, asunto, respuesta)
    elif canal == 'whatsapp':
        enviar_respuesta_por_whatsapp(destinatario, respuesta)

    return jsonify({"ok": True})

# Genera automáticamente un borrador de presupuesto a partir de un mensaje recibido
@app.route("/generar_presupuesto_automatico", methods=["POST"])
def generar_presupuesto_automatico():
    data = request.get_json()
    id_mensaje = data.get("id_mensaje")
    canal = data.get("canal")

    if not id_mensaje or not canal:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        if canal == "correo":
            mensajes = obtener_correos()
            mensaje = next((m for m in mensajes if str(m.get("id_correo")) == str(id_mensaje)), None)
        elif canal == "whatsapp":
            mensajes = obtener_whatsapps()
            mensaje = next((m for m in mensajes if str(m.get("id_whatsapp")) == str(id_mensaje)), None)
        else:
            return jsonify({"error": "Canal no válido"}), 400

        if not mensaje:
            return jsonify({"error": "Mensaje no encontrado"}), 404

        generar_borrador_presupuesto_automatico(mensaje, canal)

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Aprueba un presupuesto previamente generado y mueve el PDF a la carpeta correspondiente
@app.route('/api/aprobar_presupuesto', methods=['POST'])
def aprobar_presupuesto():
    data = request.get_json()

    id_trabajo = data.get("id_trabajo")
    if not id_trabajo:
        return jsonify({"error": "Falta id_trabajo"}), 400

    try:
        presupuesto = obtener_presupuesto_por_id_trabajo(id_trabajo)
        if not presupuesto:
            return jsonify({"error": "Presupuesto no encontrado"}), 404

        ruta_pdf_antigua = presupuesto["ruta_documento_pdf"]
        ruta_word = presupuesto["ruta_documento_word"]
        canal = presupuesto["canal"]
        destinatario = presupuesto["identificador_cliente"]

        if not canal or not destinatario:
            return jsonify({"error": "Faltan datos de canal o destinatario"}), 400

        # Mover PDF
        import os, shutil
        path_pdf_origen = os.path.join("Scripts", ruta_pdf_antigua.replace("/", os.sep))
        nombre_pdf = os.path.basename(path_pdf_origen)
        path_pdf_destino = os.path.join("Scripts", "Data", "Presupuestos", "Revisado", nombre_pdf)
        shutil.move(path_pdf_origen, path_pdf_destino)

        # Borrar Word si existe
        if ruta_word:
            path_word = os.path.join("Scripts", ruta_word.replace("/", os.sep))
            if os.path.exists(path_word):
                os.remove(path_word)

        # Actualizar en BBDD
        ruta_pdf_relativa_nueva = os.path.relpath(path_pdf_destino, "Scripts").replace(os.sep, "/")
        marcar_presupuesto_como_revisado(id_trabajo, ruta_pdf_relativa_nueva)

        # Enviar confirmación
        mensaje = "Adjuntamos el presupuesto aprobado. Gracias por contar con nosotros."
        if canal == "correo":
            insertar_mensaje_correo_generado(destinatario, "Presupuesto aprobado", mensaje, ruta_adjunto=ruta_pdf_relativa_nueva)
        elif canal == "whatsapp":
            insertar_mensaje_whatsapp_generado(destinatario, mensaje, ruta_adjunto=ruta_pdf_relativa_nueva)
        else:
            return jsonify({"error": "Canal no válido"}), 400
        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Genera una factura a partir de un pedido manual
@app.route('/api/generar_factura', methods=['POST'])
def api_generar_factura():
    pedido = request.get_json()
    if not pedido:
        return jsonify({"error": "Falta contenido JSON"}), 400

    id_trabajo = pedido.get("id_trabajo")
    if not id_trabajo:
        return jsonify({"error": "Falta id_trabajo"}), 400

    config = ConfiguracionFactura()
    ruta_docx, ruta_pdf, id_trabajo = generar_factura(pedido, config, id_trabajo)

    # Guardar fecha de modificación
    actualizar_fecha_modificacion(id_trabajo)

    return jsonify({
        "ruta_word": ruta_docx,
        "ruta_pdf": ruta_pdf,
        "id_trabajo": id_trabajo
    })

# Envía una propuesta de cita y actualiza el estado del cliente a 'esperando respuesta'
@app.route("/api/enviar_propuesta_cita", methods=["POST"])
def api_enviar_propuesta_cita():
    try:
        datos = request.get_json()

        canal = datos.get("canal")
        remitente = datos.get("identificador_cliente")
        mensaje = datos.get("mensaje")

        if not canal or not remitente or not mensaje:
            return jsonify({"ok": False, "error": "Faltan datos requeridos"}), 400

        # --- Enviar mensaje según el canal ---
        if canal == "correo":
            insertar_mensaje_correo_generado(destinatario=remitente, asunto="Propuesta de cita", mensaje=mensaje)
            actualizar_estado_conversacion_por_remitente(remitente, "correo", True)

        elif canal == "whatsapp":
            insertar_mensaje_whatsapp_generado(destinatario=remitente, mensaje=mensaje)
            actualizar_estado_conversacion_por_remitente(remitente, "whatsapp", True)

        else:
            return jsonify({"ok": False, "error": f"Canal no reconocido: {canal}"}), 400

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Aprueba una factura generada y archiva el documento como revisado
@app.route('/api/aprobar_factura', methods=['POST'])
def aprobar_factura():

    data = request.get_json()

    id_trabajo = data.get("id_trabajo")
    if not id_trabajo:
        return jsonify({"error": "Falta id_trabajo"}), 400

    try:
        factura = obtener_factura_por_id_trabajo(id_trabajo)
        if not factura:
            return jsonify({"error": "Factura no encontrada"}), 404

        ruta_pdf_antigua = factura["ruta_documento_pdf"]
        ruta_word = factura["ruta_documento_word"]
        canal = factura["canal"]
        destinatario = factura["identificador_cliente"]

        if not canal or not destinatario:
            return jsonify({"error": "Faltan datos de canal o destinatario"}), 400

        # Mover PDF
        path_pdf_origen = os.path.join("Scripts", ruta_pdf_antigua.replace("/", os.sep))
        nombre_pdf = os.path.basename(path_pdf_origen)
        path_pdf_destino = os.path.join("Scripts", "Data", "Facturas", "Revisado", nombre_pdf)
        shutil.move(path_pdf_origen, path_pdf_destino)

        # Borrar Word si existe
        if ruta_word:
            path_word = os.path.join("Scripts", ruta_word.replace("/", os.sep))
            if os.path.exists(path_word):
                os.remove(path_word)

        # Actualizar en BBDD
        ruta_pdf_relativa_nueva = os.path.relpath(path_pdf_destino, "Scripts").replace(os.sep, "/")
        marcar_factura_como_revisada(id_trabajo, ruta_pdf_relativa_nueva)

        # Enviar mensaje
        mensaje = "Adjuntamos la factura final. Gracias por contar con nosotros."

        if canal == "correo":
            insertar_mensaje_correo_generado(destinatario, "Factura final", mensaje, ruta_adjunto=ruta_pdf_relativa_nueva)
        elif canal == "whatsapp":
            insertar_mensaje_whatsapp_generado(destinatario, mensaje, ruta_adjunto=ruta_pdf_relativa_nueva)
        else:
            return jsonify({"error": "Canal no válido"}), 400

        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Intenta generar automáticamente una factura si el cliente tiene solo un presupuesto firmado
@app.route('/generar_factura_automatica', methods=['POST'])
def generar_factura_automatica():

    data = request.get_json()
    canal = data.get("canal")
    remitente = data.get("remitente")

    if not canal or not remitente:
        return jsonify({"error": "Faltan datos"}), 400

    id_cliente = obtener_id_cliente_por_remitente(remitente, canal)

    if not id_cliente:
        return jsonify({"error": "No se pudo determinar el id_cliente"}), 400

    try:
        presupuestos = obtener_presupuestos_firmados_sin_factura(id_cliente)

        if len(presupuestos) == 0:
            return jsonify({"status": "no_hay_presupuestos"})

        elif len(presupuestos) == 1:
            cliente = obtener_cliente_por_id(id_cliente)
            resultado = generar_borrador_factura_automatico(cliente, presupuestos[0])

            return jsonify({
                "status": "generado",
                "factura": resultado
            })

        else:
            return jsonify({
                "status": "multiples_presupuestos",
                "presupuestos": presupuestos
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Marca una factura como pagada y envía confirmación al cliente
@app.route("/api/marcar_factura_pagada", methods=["POST"])
def marcar_factura_pagada():
    data = request.get_json()
    id_trabajo = data.get("id_trabajo")
    canal = data.get("canal")
    identificador = data.get("identificador_cliente")

    if not id_trabajo or not canal or not identificador:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        marcar_factura_como_pagada(id_trabajo)

        mensaje = (
            "Hemos recibido el pago de su factura. "
            "Muchas gracias por confiar en nuestros servicios. "
            "¡Esperamos poder atenderle de nuevo en el futuro!"
        )

        if canal == "whatsapp":
            insertar_mensaje_whatsapp_generado(identificador, mensaje)
        else:
            insertar_mensaje_correo_generado(identificador, "Confirmación de pago", mensaje)

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Guarda un mensaje editado por el usuario, con posibilidad de marcarlo como generado por IA
@app.route('/api/guardar_mensaje_editado', methods=['POST'])
def guardar_mensaje_editado():
    data = request.get_json()
    id_respuesta = data.get('id')
    nuevo_texto = data.get('nuevo_texto')
    canal = data.get('canal')
    generado_por_ia = data.get('generado_por_ia', True)  # valor por defecto True

    if not id_respuesta or not nuevo_texto or not canal:
        return jsonify({"error": "Faltan datos necesarios"}), 400

    try:
        actualizar_texto_respuesta(id_respuesta, nuevo_texto, canal, generado_por_ia)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": "Error interno del servidor"}), 500

# Inserta uno o varios bloques personales (eventos ocupados) en el calendario
@app.route('/api/insertar_bloque_personal', methods=['POST'])
def insertar_bloque_personal():
    import datetime

    data = request.get_json()

    fecha_base = data.get("fecha")
    todo_dia = data.get("todo_dia")
    hora_inicio = data.get("hora_inicio")
    hora_fin = data.get("hora_fin")
    motivo = data.get("motivo", "Asuntos personales")
    direccion = data.get("direccion", "")
    poblacion = data.get("poblacion", "")
    repetir = data.get("repetir", False)
    repetir_hasta = data.get("repetir_hasta")
    dias_semana = data.get("dias_semana", [])

    if not fecha_base:
        return jsonify({"error": "Falta la fecha"}), 400

    if not todo_dia and (not hora_inicio or not hora_fin):
        return jsonify({"error": "Falta hora de inicio o fin"}), 400

    try:
        fechas_finales = []

        if repetir and repetir_hasta:
            fecha_inicio = datetime.datetime.strptime(fecha_base, "%Y-%m-%d").date()
            fecha_fin = datetime.datetime.strptime(repetir_hasta, "%Y-%m-%d").date()

            actual = fecha_inicio
            while actual <= fecha_fin:
                if actual.weekday() in dias_semana:
                    fechas_finales.append(actual.isoformat())
                actual += datetime.timedelta(days=1)
        else:
            fechas_finales = [fecha_base]

        bloques = []

        for fecha in fechas_finales:
            if todo_dia:
                hora = "08:00"
                duracion = 13 * 60  # 08:00 → 20:00
            else:
                h1 = datetime.datetime.strptime(hora_inicio, "%H:%M")
                h2 = datetime.datetime.strptime(hora_fin, "%H:%M")
                duracion = int((h2 - h1).total_seconds() // 60)
                hora = hora_inicio

            bloques.append({
                "fecha": fecha,
                "hora": hora,
                "duracion": duracion,
                "descripcion": motivo,
                "direccion": direccion,
                "poblacion": poblacion,
                "estado": "ocupado"
            })

        for bloque in bloques:
            insertar_bloque_personal(**bloque)

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Guarda un archivo adjunto recibido y lo asocia al mensaje original
@app.route('/api/subir_adjunto', methods=['POST'])
def subir_adjunto():
    canal = request.form.get('canal')
    id_original = request.form.get('id_correo' if canal == 'correo' else 'id_whatsapp')
    archivo = request.files.get('archivo')

    if not canal or not id_original or not archivo:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        from werkzeug.utils import secure_filename
        nombre_original = secure_filename(archivo.filename)
        nombre_archivo = f"{canal}_{id_original}_{nombre_original}"
        ruta_relativa = f"Data/Adjuntos/{nombre_archivo}"
        ruta_absoluta = os.path.join("Scripts", ruta_relativa)

        archivo.save(ruta_absoluta)

        # Actualizamos la ruta en la BBDD
        if canal == "whatsapp":
            original = obtener_datos_whatsapp_por_id(id_original)
            destinatario = original["remitente"]
            insertar_mensaje_whatsapp_generado(destinatario=destinatario, mensaje="", id_original=id_original, ruta_adjunto=ruta_relativa)
        else:
            original = obtener_datos_correo_por_id(id_original)
            destinatario = original["remitente"]
            insertar_mensaje_correo_generado(destinatario=destinatario, asunto="", mensaje="", id_original=id_original, ruta_adjunto=ruta_relativa)

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Actualiza manualmente el estado del chat de un cliente (contestado o no contestado)
@app.route('/api/actualizar_estado_chat', methods=['POST'])
def api_actualizar_estado_chat():
    data = request.get_json()
    remitente = data.get("remitente")
    canal = data.get("canal")
    chat = data.get("chat")  # debe ser 'contestado' o 'no contestado'
    id_cliente = data.get("id_cliente")

    if not remitente or not canal or chat not in ('contestado', 'no contestado'):
        return jsonify({"error": "Parámetros inválidos"}), 400

    guardar_estado_chat(remitente, canal, id_cliente, chat)

    return jsonify({"ok": True})

# Devuelve el estado conversacional de todos los clientes activos
@app.route("/api/estado_conversaciones")
def api_estado_conversaciones():
    try:
        estados = obtener_estado_conversaciones()
        return jsonify(estados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Procesa un archivo adjunto recibido y ejecuta validación por OCR para detectar firma
@app.route('/api/procesar_adjunto_firmado', methods=['POST'])
def api_procesar_adjunto_firmado():
    archivo = request.files.get("archivo")
    if not archivo:
        return jsonify({"error": "No se ha enviado archivo"}), 400

    from werkzeug.utils import secure_filename
    filename = secure_filename(archivo.filename)
    temp_path = os.path.join("Scripts", "Data", "Adjuntos", filename)
    archivo.save(temp_path)

    id_trabajo, error = procesar_archivo_firmado(temp_path)
    if error:
        return jsonify({"match": False, "mensaje": error}), 200
    return jsonify({"match": True, "id_trabajo": id_trabajo}), 200

# Revisa un archivo adjunto previamente subido y verifica si corresponde a una firma válida
@app.route("/api/revisar_adjuntos_firmados", methods=["POST"])
def revisar_adjuntos_firmados():
    datos = request.get_json()

    canal = datos.get("canal")
    id_mensaje = datos.get("id_mensaje")

    if canal == "correo":
        mensaje = obtener_datos_correo_por_id(id_mensaje)
    else:
        mensaje = obtener_datos_whatsapp_por_id(id_mensaje)


    ruta_origen = mensaje.get("ruta_adjunto")
    if not ruta_origen or not os.path.isfile(ruta_origen):
        return jsonify({"ok": False, "error": "Archivo original no encontrado"})

    # Copiar a carpeta estándar interna
    nombre_original = os.path.basename(ruta_origen)
    nuevo_nombre = f"{canal}_{id_mensaje}_{nombre_original}"
    ruta_local = os.path.join("Scripts", "Data", "Adjuntos", nuevo_nombre)

    os.makedirs(os.path.dirname(ruta_local), exist_ok=True)
    shutil.copy(ruta_origen, ruta_local)

    #  Ejecutar OCR en la nueva ruta
    from Scripts.procesador_firmas import procesar_archivo_firmado
    id_trabajo, error = procesar_archivo_firmado(ruta_local)

    if id_trabajo:
        nueva_ruta = f"Data/Presupuestos/Firmado/firmado_{id_trabajo}.pdf"
        if canal == "correo":
            actualizar_ruta_adjunto_correo(id_mensaje, nueva_ruta)
        else:
            actualizar_ruta_adjunto_whatsapp(id_mensaje, nueva_ruta)
            
        #  Agradecimiento y marcar como contestado
        mensaje_gracias = "Hemos recibido el presupuesto firmado. Muchas gracias por su confirmación."

        actualizar_estado_mensaje(id_mensaje, canal, "contestado")

        if canal == "whatsapp":
            insertar_mensaje_whatsapp_generado(destinatario=mensaje["remitente"], mensaje=mensaje_gracias, id_original=id_mensaje)
        else:
            insertar_mensaje_correo_generado(destinatario=mensaje["remitente"], asunto="Presupuesto firmado", mensaje=mensaje_gracias, id_original=id_mensaje)
        return jsonify({"ok": True, "id_trabajo": id_trabajo})

    return jsonify({"ok": False, "error": error})

# Actualiza los datos de un cliente desde el panel de edición
@app.route("/api/actualizar_cliente", methods=["POST"])
def actualizar_cliente():
    data = request.get_json()
    actualizar_cliente(data)
    return jsonify({"ok": True})


# ------------------------------------ FUNCIONES EN SEGUNDO PLANO  -------------------------------------

# Procesamiento automático de mensajes pendiente
def procesar_correos():
    while True:
        try:
            volcar_correos_no_leidos()
            pendientes = obtener_correos_pendientes()

            for original in pendientes:
                remitente = original["remitente"]

                # Comprobación de ficha pendiente
                mensaje_esperado = obtener_mensaje_esperando_datos(remitente, canal="correo")

                if mensaje_esperado:
                    id_mensaje_original = mensaje_esperado.get("id_correo")

                    id_cliente = completar_ficha_cliente(
                        original["mensaje"], id_mensaje_original=id_mensaje_original, canal="correo", remitente_original=remitente
                    )

                    desmarcar_esperando_datos_cliente_correo(id_mensaje_original)
                    guardar_estado_chat(remitente, "correo", id_cliente, "contestado")
                    generar_borrador_presupuesto_automatico(original, canal="correo")
                    marcar_correo_como_contestado(id_mensaje_original)
                    marcar_correo_como_contestado(original["id_correo"])
                    continue

                # Comprobación de respuesta a propuesta de cita
                if esta_esperando_datos(remitente, "correo"):
                    from Scripts.generador_respuesta import interpretar_mensaje_cita
                    resultado = interpretar_mensaje_cita(original["mensaje"])
                    if resultado["cita_confirmada"]:
                        id_cliente = obtener_id_cliente_por_remitente(remitente, "correo")
                        insertar_cita_en_horarios(id_cliente, resultado["fecha"], resultado["hora"], resultado["duracion"])
                        desmarcar_esperando_datos(remitente, "correo")
                        marcar_correo_como_contestado(original["id_correo"])
                        continue

                respuesta = generar_respuesta_automatica(original['mensaje'], via_comunicacion="correo")
                original_completo = obtener_datos_correo_por_id(original["id_correo"])

                if original_completo:
                    insertar_respuesta_automatica_correos(original_completo, respuesta)
                    marcar_correo_como_contestado(original["id_correo"])
                else:
                    print(f"Error: No se pudo recuperar el correo completo con id {original['id_correo']}")

            time.sleep(30)
        except Exception as e:
            time.sleep(60)

def procesar_whatsapps():
    # Lanza el microservicio de escucha de WhatsApp Web
    import subprocess
    import os
    ruta_script = os.path.join(os.path.dirname(__file__), "Scripts", "whatsapp_service", "index.js")
    if os.path.exists(ruta_script):
        subprocess.Popen(["node", ruta_script], cwd=os.path.dirname(ruta_script))

    while True:
        try:
            pendientes = obtener_whatsapps_pendientes()

            for original in pendientes:
                remitente = original["remitente"]
                
                # Comprobación de ficha pendiente
                mensaje_esperado = obtener_mensaje_esperando_datos(remitente, canal="whatsapp")
                if mensaje_esperado:
                    id_mensaje_original = mensaje_esperado.get("id_whatsapp")
                    id_cliente = completar_ficha_cliente(
                        original["mensaje"], id_mensaje_original=id_mensaje_original, canal="whatsapp", remitente_original=remitente
                    )
                    desmarcar_esperando_datos_cliente_whatsapp(id_mensaje_original)
                    guardar_estado_chat(remitente, "whatsapp", id_cliente, "contestado")
                    generar_borrador_presupuesto_automatico(original, canal="whatsapp")
                    marcar_whatsapp_como_contestado(id_mensaje_original)
                    marcar_whatsapp_como_contestado(original["id_whatsapp"])
                    continue

                # Comprobación de respuesta a propuesta de cita
                if esta_esperando_datos(remitente, "whatsapp"):
                    from Scripts.generador_respuesta import interpretar_mensaje_cita
                    resultado = interpretar_mensaje_cita(original["mensaje"])
                    if resultado["cita_confirmada"]:
                        id_cliente = obtener_id_cliente_por_remitente(remitente, "whatsapp")

                        presupuestos_firmados = obtener_presupuestos_firmados()
                        presupuestos_cliente = [p for p in presupuestos_firmados if p["id_cliente"] == id_cliente]

                        if not presupuestos_cliente:
                            continue

                        id_trabajo = presupuestos_cliente[0]["id_trabajo"]

                        insertar_cita_en_horarios(
                            id_cliente=id_cliente,
                            id_trabajo=id_trabajo,
                            fecha=resultado["fecha"],
                            hora=resultado["hora"],
                            duracion=resultado["duracion"]
                        )
                        desmarcar_esperando_datos(remitente, "whatsapp")
                        marcar_whatsapp_como_contestado(original["id_whatsapp"])
                        continue

                respuesta = generar_respuesta_automatica(original['mensaje'], via_comunicacion="whatsapp")
                original_completo = obtener_datos_whatsapp_por_id(original["id_whatsapp"])

                if original_completo:
                    insertar_respuesta_automatica_whatsapps(original_completo, respuesta)
                    marcar_whatsapp_como_contestado(original["id_whatsapp"])
                else:
                    print(f"Error: No se pudo recuperar el WhatsApp completo con id {original['id_whatsapp']}")

            time.sleep(30)
        except Exception as e:
            time.sleep(60)


# ---------------------------------------- EJECUCIÓN DEL SERVIDOR ----------------------------------------
if __name__ == '__main__':
    import os

    PORT = 8000
    url = f"http://localhost:{PORT}"
    print(f"\n Servidor corriendo en: {url} \n")

    # Evita abrir dos veces el navegador al recargar el servidor en modo debug
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        webbrowser.open(url)

        # Lanzar procesamiento automático en segundo plano (después del navegador)
        threading.Thread(target=procesar_correos, daemon=True).start()
        threading.Thread(target=procesar_whatsapps, daemon=True).start()

    # Iniciar servidor web (esto debe ir después del hilo para no bloquearlo)
    app.run(debug=True, host='0.0.0.0', port=PORT)