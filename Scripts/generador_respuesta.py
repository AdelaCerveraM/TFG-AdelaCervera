import requests
from datetime import datetime
import json
from Scripts.generador_borrador_presupuesto import generar_borrador_presupuesto_automatico

from Scripts.bbdd import (
    obtener_datos_whatsapp_por_id,
    obtener_datos_correo_por_id,
    obtener_presupuestos_recientes_por_cliente
)
from datetime import datetime, timedelta

# ------------------------------------ PROMPTS -------------------------------------

fases = {
    "primer_contacto": "Mensaje inicial del cliente que inicia la conversación. Puede incluir una consulta, solicitud o problema general pero no habla de fechas ni visitas.",
    "primer_contacto + proponer_fecha": "Cliente que acaba de contactar y propone una visita a su domicilio para que sea posible valorar la situación.",
    "recepcion_detalles": "El cliente aporta información adicional relevante a una solicitud previa, como medidas, fotos o aclaraciones para preparar un presupuesto.",
    "respuesta_presupuesto": "Respuesta del cliente a un presupuesto enviado anteriormente. Puede aceptarlo, solicitar cambios o rechazarlo educadamente.",
    "respuesta_presupuesto + proponer_fecha": "Cliente que acepta el presupuesto o pregunta por fechas y horarios disponibles para realizar el trabajo o visita.",
    "proponer_fecha": "Solo habla de fechas o horarios.",
    "finalizado": "El trabajo ha finalizado."
    # enviar_presupuesto y enviar_factura no son fases a detectar, porque esos mensajes parten del receptor sin ninguno previo
}

prompts_por_fase = {
    "primer_contacto": """
        Instrucciones:
        - NO incluyas saludos ni despedidas.
        - NO incluyas ninguna fecha ni horario ni cita.
        - Menciona brevemente el problema (ejemplo: "sobre la persiana", "respecto a la mampara").
        - Si el mensaje es vago, pide más detalles (tipo de problema, medidas, fotos).
        - Si el mensaje es claro, confirma que prepararás un presupuesto o propondrás una visita.
        - Si el mensaje propone una visita, dile que a continuación le pasas las fechas disponibles.
        """,

    "primer_contacto + proponer_fecha": """
        Instrucciones:
        - NO incluyas saludos ni despedidas.
        - Reconoce que el cliente necesita una visita para valorar la situación.
        - Explica que se revisarán las fechas para la visita y se confirmará lo antes posible.
        - Indica que si hay cualquier inconveniente se podrá adaptar la agenda.
        - Sé profesional, amable y conciso.
        """,

    "recepcion_detalles": """
        Instrucciones:
        - NO incluyas saludos ni despedidas.
        - Escribe un mensaje corto y profesional confirmando que has recibido la información.
        - Indica que prepararás el presupuesto o contactarás para el siguiente paso.
        - Agradece la confianza y dile que esperas que el presupuesto se adapte a sus necesidades y que si tiene cualquier propuesta, se puede ajustar.
        """,

    "enviar_presupuesto": """
        Instrucciones:
        - NO incluyas saludos ni despedidas.
        - Escribe un mensaje confirmando que el presupuesto está adjunto o listo.
        - Invita a revisarlo y a comunicar cualquier duda o cambio.
        - No incluyas precios o listas, solo confirma y mantén el tono amable.
        """,

    "respuesta_presupuesto": """
        Instrucciones:
        - NO incluyas saludos ni despedidas.
        - Si lo acepta, agradécele y pregunta qué día y hora prefiere para la visita.
        - Si pide cambios, confirma que actualizarás el presupuesto y lo enviarás de nuevo.
        - Si lo rechaza, agradécele educadamente y ofrece ayuda futura.
    """,

    "respuesta_presupuesto + proponer_fecha": """
        Instrucciones:
        - NO incluyas saludos ni despedidas.
        - Reconoce la aceptación del presupuesto y la consulta o propuesta de fechas.
        - Indica que se revisarán las fechas propuestas y se confirmará la visita.
        - Menciona que se adaptarán a la agenda del cliente si hay algún problema.
        - Sé profesional, amable y breve.
        """,

    "proponer_fecha": """
        Instrucciones:
        - NO incluyas saludos ni despedidas.
        - NO incluyas ningún dato sobre fechas concretas.
        - Si el cliente ha propuesto fechas para la visita, responde indicando que se revisarán esas fechas y se confirmará la visita.
        - Si el cliente no ha propuesto fechas, responde indicando que se revisará la disponibilidad y a continuación le pasaremos las fechas disponibles.
        - Indica que si hay cualquier problema, se puede analizar la situación para adaptarte a su agenda.
        - Sé profesional, amable y breve.
    """,

    "enviar_factura": """
        Instrucciones:
        - NO incluyas saludos ni despedidas.
        - Confirma que la factura está enviada, menciona el método de pago (transferencia bancaria) y agradece su confianza.
    """,

    "finalizado": """
        Instrucciones:
        - Se confirma que se el pago ha llegado correctamente.
        - Agradece la confianza del cliente y ofrece tu ayuda para futuras necesidades.
        - La conversación se cierra con agradecimientos y posible oferta de ayuda futura.
        - No lo hagas muy largo (máximo 4 oraciones)
    """
}


# ------------------------------------ FUNCIONES AUXILIARES -------------------------------------

# Genera una respuesta textual a partir de un prompt, usando el modelo local 'mistral' vía la API de Ollama
def generar_respuesta_ollama(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False
        }
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()

# Clasifica un mensaje en una de las fases conversacionales definidas, utilizando un modelo de IA local
def clasificar_fase(mensaje):
    # Convierte dict a lista de fases para mostrar en prompt
    fases_listado = ", ".join(fases.keys())
    prompt_clasificacion = f"""
        Eres un asistente de una pequeña empresa de reparaciones del hogar. Clasifica este mensaje en una de estas fases exactas: {fases_listado}.

        Mensaje: "{mensaje}"

        Analiza todas las opciones antes de elegir. NO debes dar fechas, ni horas, ni propuestas de horarios. Responde SOLO con el nombre de la fase.
        """

    respuesta = generar_respuesta_ollama(prompt_clasificacion)
    if respuesta in fases:
        return respuesta
    return "primer_contacto"

# Genera un saludo y despedida personalizados según canal, fase de la conversación, y hora del día
def obtener_saludo_y_despedida(via_comunicacion, nombre_empresa, fase, nombre_cliente=None):
    # Obtener hora actual para saludo
    ahora = datetime.now()
    hora = ahora.hour
    if 6 <= hora < 12:
        saludo_hora = "Buenos días"
    elif 12 <= hora < 21:
        saludo_hora = "Buenas tardes"
    else:
        saludo_hora = "Buenas noches"

    # Distinguimos entre correo y whatsapp
    via = via_comunicacion.lower()

    saludo = ""
    despedida = ""

    # -------- CORREO --------
    if via == "correo":
        # SALUDO (en función de hora y nombre)
        # Si es el primer mensaje se incluye agradecimiento
        if fase == "primer_contacto":
            if nombre_cliente:
                saludo = f"{saludo_hora} {nombre_cliente}, \nMuchas gracias por confiar en nosotros de nuevo."
            else:
                saludo = f"{saludo_hora}, \nMuchas gracias por confiar en nosotros"
        # Si no es el primer, solo se saluda
        else:
            saludo = f"{saludo_hora} {nombre_cliente}," if nombre_cliente else f"{saludo_hora},"

        # DESPEDIDA
        despedida = f"Atentamente,\n{nombre_empresa}"

    # -------- WHATSAPP --------
    elif via == "whatsapp":
        # SALUDO SOLO SI ES PRIMER MENSAJE (en función de hora y nombre)
        if fase == "primer_contacto":
            if nombre_cliente:
                saludo = f"{saludo_hora} {nombre_cliente}, muchas gracias por contactar con nosotros de nuevo."
            else:
                saludo = f"{saludo_hora}, muchas gracias por contactar con nosotros."

    else:
        # Default saludo genérico
        saludo = f"Hola."
        despedida = "Saludos."

    return saludo, despedida

# Interpreta un mensaje libre del cliente para detectar si contiene una confirmación de cita, extrayendo fecha, hora y duración
def interpretar_mensaje_cita(mensaje):
    prompt = f"""
        Eres un asistente experto en coordinar citas. Lee el siguiente mensaje del cliente y responde en JSON indicando si contiene una confirmación clara de una cita y, si es posible, la fecha y hora:

        Mensaje: "{mensaje}"

        Tu respuesta debe tener este formato exacto:
        {{
        "cita_confirmada": true/false,
        "fecha": "YYYY-MM-DD" o null,
        "hora": "HH:MM" o null,
        "duracion": minutos (entero, estimado, por ejemplo 60)
        }}

        Si no hay confirmación clara o no puedes inferir la fecha/hora, pon cita_confirmada: false.
        No escribas nada más.
        """

    try:
        respuesta = generar_respuesta_ollama(prompt)
        resultado = json.loads(respuesta)
    except Exception as e:
        resultado = {"cita_confirmada": False}

    return resultado


# ------------------------------------ FUNCIÓN PRINCIPAL -------------------------------------

def generar_respuesta_automatica(mensaje_cliente, via_comunicacion="whatsapp", nombre_empresa="Empresa Demo", nombre_cliente=None):
    # Detectar fase
    fase = clasificar_fase(mensaje_cliente)
    prompt_template = prompts_por_fase.get(fase, prompts_por_fase["primer_contacto"])
    prompt = prompt_template.format(mensaje=mensaje_cliente, saludo="")

    # Crear prompt final para generar respuesta
    inicio_comun = (
        'Eres un asistente que responde en nombre de una pequeña empresa de reparaciones del hogar. '
        f'Un cliente ha escrito: "{mensaje_cliente}"\n'
        'Escribe una respuesta corta, cálida, profesional y amable en español, siguiendo las instrucciones dadas a continuación:\n'
    )

    respuesta_ollama = generar_respuesta_ollama(inicio_comun + prompt)

    # Añadir saludo y despedida
    saludo, despedida = obtener_saludo_y_despedida(via_comunicacion, nombre_empresa, fase, nombre_cliente)

    if via_comunicacion.lower() == "correo":
        respuesta_final = f"{saludo}\n\n{respuesta_ollama}\n\n{despedida}"
    else:
        if fase == "finalizado":
            respuesta_final = respuesta_ollama
        else:
            respuesta_final = f"{saludo}\n\n{respuesta_ollama}"

    # LLAMADA AUTOMÁTICA SI LA FASE ES "recepcion_detalles"
    if fase == "recepcion_detalles":
        try:
            mensaje_dict = {
                "remitente": nombre_cliente or "(desconocido)",
                "mensaje": mensaje_cliente,
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # Obtener el mensaje completo para acceder a id_cliente
            if via_comunicacion == "whatsapp":
                mensaje_completo = obtener_datos_whatsapp_por_id(mensaje_cliente.get("id_whatsapp", -1))
            else:
                mensaje_completo = obtener_datos_correo_por_id(mensaje_cliente.get("id_correo", -1))

            id_cliente = mensaje_completo.get("id_cliente") if mensaje_completo else None

            if id_cliente:
                presupuestos = obtener_presupuestos_recientes_por_cliente(id_cliente)
                if presupuestos:
                    fecha_ultimo = presupuestos[0]["fecha_creacion"]
                    if isinstance(fecha_ultimo, str):
                        fecha_ultimo = datetime.strptime(fecha_ultimo, "%Y-%m-%d %H:%M:%S")

                    if datetime.now() - fecha_ultimo < timedelta(minutes=15):
                        return  # No generar

            generar_borrador_presupuesto_automatico(mensaje_completo, via_comunicacion)

        except Exception as e:
            print("Error al generar el borrador de presupuesto automáticamente:", e)
        
    return respuesta_final
