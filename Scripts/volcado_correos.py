import imaplib
import email
from email.header import decode_header
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
import os
import ssl

# Cargar variables de entorno
dotenv_path = os.path.join(os.path.dirname(__file__), ".env.correo")
load_dotenv(dotenv_path=dotenv_path)
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

load_dotenv(dotenv_path=".env.bbdd")
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "empresa_demo")
}

IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# Limpia un texto recibido, decodificándolo si está en formato bytes
def limpiar(texto):
    if isinstance(texto, bytes):
        return texto.decode(errors='replace')
    return texto

# Procesa un mensaje de correo electrónico (objeto email.message) y extrae sus campos relevantes
def procesar_correo(msg):
    datos = {}

    # Fecha
    date_tuple = email.utils.parsedate_tz(msg.get("Date"))
    if date_tuple:
        fecha_local = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
        datos["fecha"] = fecha_local.strftime("%Y-%m-%d %H:%M:%S")
    else:
        datos["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Remitente
    from_raw = msg.get("From")
    if not from_raw:
        datos["remitente"] = "(Remitente desconocido)"
    else:
        try:
            remitente_raw, encoding = decode_header(from_raw)[0]
            datos["remitente"] = limpiar(remitente_raw)
            
            # Ignorar remitentes automáticos tipo 'noreply'
            remitente = datos["remitente"].lower()
            if "noreply" in remitente or "no-reply" in remitente or "no_reply" in remitente:
                return None

        except Exception as e:
            print(f"Error procesando remitente: {e}")
            datos["remitente"] = "(Remitente ilegible)"


    # Asunto
    subject_raw = msg.get("Subject")
    if not subject_raw:
        datos["asunto"] = "(Sin asunto)"
    else:
        try:
            asunto_raw, encoding = decode_header(subject_raw)[0]
            datos["asunto"] = limpiar(asunto_raw)
        except Exception as e:
            print(f"Error procesando asunto: {e}")
            datos["asunto"] = "(Asunto ilegible)"

    # Cuerpo
    datos["cuerpo"] = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition"))
                if "attachment" not in disp and ctype in ["text/plain", "text/html"]:
                    datos["cuerpo"] = part.get_payload(decode=True).decode(errors='replace')
                    break
        else:
            datos["cuerpo"] = msg.get_payload(decode=True).decode(errors='replace')
    except Exception as e:
        print(f"Error procesando cuerpo del mensaje: {e}")
        datos["cuerpo"] = ""

    # Identificador único para evitar duplicados     
    datos["identificador_unico"] = msg.get("Message-ID", "").strip()
    return datos

# Inserta un correo procesado en la base de datos, evitando duplicados por identificador único
def insertar_en_mysql(datos):
    if not datos.get("identificador_unico"):
        print("Correo sin Message-ID, se omite por seguridad.")
        return

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    # Verificar si ya existe
    cursor.execute("SELECT COUNT(*) FROM correos WHERE identificador_unico = %s", (datos["identificador_unico"],))
    if cursor.fetchone()[0] > 0:
        cursor.close()
        conn.close()
        return

    cursor.execute("""
        INSERT INTO correos (remitente, destinatario, asunto, mensaje, fecha, tipo_mensaje, estado, identificador_unico)
        VALUES (%s, %s, %s, %s, %s, 'entrante', 'pendiente', %s)
    """, (
        str(datos.get("remitente") or ""),
        EMAIL, 
        str(datos.get("asunto") or ""),
        str(datos.get("cuerpo") or ""),
        str(datos.get("fecha") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        str(datos.get("identificador_unico"))
    ))

    conn.commit()
    cursor.close()
    conn.close()

# Devuelve la fecha del último correo entrante registrado en la base de datos, en formato IMAP
def obtener_fecha_ultimo_correo():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        # Filtramos, además, para evitar los correos de creación de cuenta y pruebas iniciales
        cursor.execute("""
            SELECT MAX(fecha) FROM correos 
            WHERE tipo_mensaje = 'entrante' AND fecha >= '2025-05-17'  
        """)
        resultado = cursor.fetchone()
        cursor.close()
        conn.close()
        if resultado and resultado[0]:
            return resultado[0].strftime("%d-%b-%Y")  # Formato para IMAP (ej: '16-May-2025')
    except Exception as e:
        print("No se pudo obtener la última fecha de correo:", e)
    return None

# Conecta a la bandeja de entrada, recupera correos no leídos recientes y los vuelca a la base de datos
def volcar_correos_no_leidos():
    contexto = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=contexto)

    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")

    fecha_desde = obtener_fecha_ultimo_correo()
    if fecha_desde:
        status, messages = mail.search(None, f'(SINCE "{fecha_desde}")')
    else:
        status, messages = mail.search(None, "UNSEEN")

    if status != "OK":
        print("No se pudieron buscar mensajes.")
        return

    for num in messages[0].split():
        res, data = mail.fetch(num, "(RFC822)")
        if res != "OK":
            print(f"No se pudo leer el mensaje {num.decode()}")
            continue

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        datos = procesar_correo(msg)
        if datos is None:
            continue

        try:
            insertar_en_mysql(datos)
            mail.store(num, '+FLAGS', '\\Seen')
        except Exception as e:
            print("[ERROR] Error al guardar el correo:")
            import traceback
            traceback.print_exc()

    mail.logout()