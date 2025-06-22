import os
import requests

from dotenv import load_dotenv
import mysql.connector

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Cargar variables de entorno
load_dotenv(".env.correo")
load_dotenv(".env.bbdd")

# Configuración de correo
SMTP_USER = os.getenv("EMAIL")
SMTP_PASS = os.getenv("PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# Configuración de base de datos
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}

# Conexión a la base de datos
conn = mysql.connector.connect(**MYSQL_CONFIG)
cursor = conn.cursor(dictionary=True)

# Envía un correo electrónico con asunto, cuerpo y adjunto opcional a una dirección predefinida
def enviar_respuesta_por_correo(asunto, cuerpo, adjunto=None):
    # destinatario = mensaje_original["remitente"]  # <- En producción se enviaría a la dirección del cliente
    destinatario = "adelacerveram@gmail.com"

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain"))

    if adjunto and os.path.exists(adjunto):
        from email.mime.application import MIMEApplication
        with open(adjunto, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(adjunto))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(adjunto)}"'
            msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    except Exception as e:
        print("Error al enviar correo:", e)

# Envía un mensaje de WhatsApp mediante el microservicio local en Node.js
def enviar_respuesta_por_whatsapp(numero, mensaje):
    try:
        url = "http://localhost:3001/enviar_mensaje"
        datos = {"numero": numero, "mensaje": mensaje}
        respuesta = requests.post(url, json=datos)
        if respuesta.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        return False