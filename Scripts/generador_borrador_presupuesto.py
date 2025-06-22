import json
import pgeocode
import re

from Scripts.generador_presupuesto import generar_presupuesto, ConfiguracionPresupuesto
from Scripts.envio_respuesta_aprobada import enviar_respuesta_por_correo
from Scripts.bbdd import (
    generar_nuevo_id_trabajo,
    asociar_trabajo_a_cliente,
    insertar_presupuesto,
    obtener_correos,
    obtener_whatsapps,
    insertar_mensaje_whatsapp_generado,
    insertar_mensaje_correo_generado,
    crear_ficha_cliente, 
    marcar_esperando_datos_cliente_correo,
    marcar_esperando_datos_cliente_whatsapp,
    guardar_estado_chat,
    obtener_id_cliente_por_remitente    

)

# Obtiene el código postal asociado a una población española usando pgeocode
def obtener_cp_por_poblacion(poblacion):
    nomi = pgeocode.Nominatim('es')
    codigos = nomi.query_location(poblacion)
    
    if codigos is not None and not codigos.empty:
        cp = codigos.iloc[0]  # Primer resultado
        return str(cp.postal_code).strip()
    return ""

# Extrae los datos personales del cliente desde un mensaje usando un modelo de IA local
def extraer_datos_cliente_desde_mensaje(mensaje):
    from Scripts.generador_respuesta import generar_respuesta_ollama
    prompt = f"""
        Extrae los siguientes datos del siguiente mensaje en español:

        - nombre completo
        - teléfono
        - DNI
        - dirección
        - población
        - provincia

        El mensaje del cliente es:

        \"{mensaje}\"

        Devuélvelo en formato JSON con las claves exactas:
        {{
        "nombre": "...",
        "telefono": "...",
        "dni": "...",
        "direccion": "...",
        "poblacion": "...",
        "provincia": "..."
        }}
        Si no puedes encontrar algún dato, déjalo como cadena vacía.
        """

    respuesta = generar_respuesta_ollama(prompt)
    try:
        try:
            respuesta_limpia = re.sub(r'//.*$', '', respuesta, flags=re.MULTILINE)
            datos = json.loads(respuesta_limpia)
            return {
                "nombre": datos.get("nombre", ""),
                "telefono": datos.get("telefono", ""),
                "dni": datos.get("dni", ""),
                "direccion": datos.get("direccion", ""),
                "poblacion": datos.get("poblacion", ""),
                "provincia": datos.get("provincia", ""),
                "cp": obtener_cp_por_poblacion(datos.get("poblacion", ""))
            }

        except:
            respuesta_limpia = re.sub(r'//.*$', '', respuesta, flags=re.MULTILINE)
            datos = json.loads(respuesta_limpia)
            return {
                "nombre": datos.get("nombre", ""),
                "telefono": datos.get("telefono", ""),
                "dni": datos.get("dni", ""),
                "direccion": datos.get("direccion", ""),
                "poblacion": datos.get("poblacion", ""),
                "provincia": datos.get("provincia", ""),
                "cp": ""
            }
    except Exception as e:
        return {
            "nombre": "",
            "telefono": "",
            "dni": "",
            "direccion": "",
            "poblacion": "",
            "provincia": "",
            "cp": obtener_cp_por_poblacion(datos.get("poblacion", ""))
        }

# Completa automáticamente la ficha del cliente en base a su mensaje, registrando su estado si es necesario
def completar_ficha_cliente(mensaje_cliente, id_mensaje_original=None, canal=None, remitente_original=None):
    datos = extraer_datos_cliente_desde_mensaje(mensaje_cliente)
    id_cliente, _ = crear_ficha_cliente(datos)

    if canal and remitente_original:
        guardar_estado_chat(remitente_original, canal, id_cliente, "contestado")

    return id_cliente

# Extrae los datos necesarios para generar un presupuesto a partir del historial reciente de conversación
def extraer_datos_para_presupuesto(mensajes_contexto):
    from Scripts.generador_respuesta import generar_respuesta_ollama
    from Scripts.generador_respuesta import clasificar_fase

    # Orden cronológico
    mensajes_ordenados = sorted(mensajes_contexto, key=lambda m: m["fecha"])

    # Buscar último mensaje entrante clasificado como "primer_contacto"
    indice_inicio = None
    for i in reversed(range(len(mensajes_ordenados))):
        m = mensajes_ordenados[i]
        if m["tipo_mensaje"] == "entrante":
            fase = clasificar_fase(m["mensaje"])
            if fase == "primer_contacto":
                indice_inicio = i
                break

    if indice_inicio is not None:
        mensajes_relevantes = mensajes_ordenados[indice_inicio:]
    else:
        mensajes_relevantes = mensajes_ordenados[-10:]

    texto_conversacion = "\n".join(
        f"{m['fecha']} - {m['remitente']}: {m['mensaje']}" for m in mensajes_relevantes
    )

    prompt = f"""
        Eres un asistente que ayuda a preparar presupuestos a partir de conversaciones entre un cliente y una empresa de servicios técnicos (como reparación de persianas, fontanería, etc.).

        Extrae los siguientes elementos de la conversación. Usa solo información concreta, evita suposiciones:

        1. descripcion: resumen breve del trabajo a realizar. SIN dirección ni el nombre del cliente.
        2. conceptos: lista de objetos con {{"concepto", "cantidad", "precio_unitario"}}. Si no se indica precio, pon 0.0.
        3. condiciones: lista de frases del tipo "Pago al finalizar", "Garantía de 6 meses", etc.

        La conversación es:

        {texto_conversacion}

        Devuelve los datos en formato JSON con esta estructura exacta:

        {{
        "descripcion": "...",
        "conceptos": [
            {{"concepto": "...", "cantidad": 1, "precio_unitario": 0.0}}
        ],
        "condiciones": ["...", "..."]
        }}
    """

    respuesta = generar_respuesta_ollama(prompt)

    try:
        respuesta_limpia = re.sub(r'//.*', '', respuesta)  # elimina comentarios tipo "// ..."
        datos = json.loads(respuesta_limpia)
        return (
            datos.get("descripcion", "-"),
            datos.get("conceptos", []),
            datos.get("condiciones", [])
        )
    except Exception as e:
        return "-", [], []

# Genera automáticamente un borrador de presupuesto a partir de un mensaje original, con validación de cliente
def generar_borrador_presupuesto_automatico(mensaje_original, canal):
    id_cliente = mensaje_original.get("id_cliente")

    if not id_cliente:
        remitente = mensaje_original["remitente"]
        id_cliente = obtener_id_cliente_por_remitente(remitente, canal)

        if id_cliente:
            mensaje_original["id_cliente"] = id_cliente

        else:
            # Cliente no registrado → pedir datos y marcar esperando
            texto_pedir_datos = (
                "Para poder completar su ficha de cliente y gestionar correctamente el presupuesto, "
                "¿podría indicarnos su nombre completo, teléfono, correo, DNI y dirección?"
            )

            if canal == "correo":
                enviar_respuesta_por_correo("Solicitud de datos para presupuesto", texto_pedir_datos)
                id_original = mensaje_original.get("id_correo")
                destinatario = mensaje_original.get("remitente")
                if destinatario:
                    insertar_mensaje_correo_generado(
                        destinatario=destinatario,
                        asunto="Solicitud de datos para presupuesto",
                        mensaje=texto_pedir_datos,
                        id_original=id_original
                    )
                    marcar_esperando_datos_cliente_correo(id_original)
            else:
                id_original = mensaje_original.get("id_whatsapp")
                if id_original:
                    insertar_mensaje_whatsapp_generado(mensaje_original["remitente"], texto_pedir_datos, id_original)
                    marcar_esperando_datos_cliente_whatsapp(id_original)

            return

    # Cliente ya existe → generar presupuesto
    id_trabajo = generar_nuevo_id_trabajo()
    asociar_trabajo_a_cliente(id_cliente, id_trabajo)

    remitente = mensaje_original["remitente"]
    if canal == "correo":
        mensajes = obtener_correos()
        mensajes_hilo = [m for m in mensajes if m["remitente"] == remitente or m["destinatario"] == remitente]
    else:
        mensajes = obtener_whatsapps()
        mensajes_hilo = [m for m in mensajes if m["remitente"] == remitente or m["destinatario"] == remitente]

    descripcion, conceptos, condiciones = extraer_datos_para_presupuesto(mensajes_hilo)

    # Limpiar las condiciones de comillas y saltos vacíos
    if isinstance(condiciones, list):
        condiciones = [c.strip().strip('"').strip("'") for c in condiciones if isinstance(c, str) and c.strip()]
    elif isinstance(condiciones, str):
        condiciones = [line.strip().strip('"').strip("'") for line in condiciones.splitlines() if line.strip()]

    pedido = {
        "id_cliente": id_cliente,
        "descripcion": descripcion,
        "conceptos": conceptos,
        "condiciones": condiciones  # ya lista limpia
    }

    config = ConfiguracionPresupuesto()
    ruta_docx, ruta_pdf, _ = generar_presupuesto(pedido, config, id_trabajo)

    # Convertir a string para guardar en la BBDD (una línea por condición)
    condiciones_para_guardar = '\n'.join(condiciones)

    insertar_presupuesto(
        id_cliente=id_cliente,
        id_trabajo=id_trabajo,
        descripcion=descripcion,
        conceptos=conceptos,
        condiciones=condiciones_para_guardar,
        ruta_docx=ruta_docx,
        ruta_pdf=ruta_pdf,
        canal=canal,
        identificador_cliente=remitente
    )