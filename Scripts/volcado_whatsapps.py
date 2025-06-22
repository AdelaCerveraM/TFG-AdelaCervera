import requests

URL_INSERCION = "http://localhost:8000/api/insertar_whatsapp"

# Envía un mensaje de WhatsApp recibido al backend mediante una petición POST a la API de inserción
def volcar_whatsapp_desde_api(remitente, mensaje):
    try:
        data = {
            "remitente": remitente,
            "mensaje": mensaje
        }
        response = requests.post(URL_INSERCION, json=data)
        if response.status_code == 200:
            print(f"Mensaje insertado correctamente: {remitente} - {mensaje}")
        else:
            print(f"Error al insertar mensaje: {response.text}")
    except Exception as e:
        print(f"Error en volcado_whatsapps: {e}")