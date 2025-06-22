import os
import pytesseract
import cv2
import shutil
from pdf2image import convert_from_path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from Scripts.bbdd import obtener_documentos, marcar_presupuesto_como_firmado

# Extrae el texto de un archivo mediante OCR, ya sea PDF multipágina o imagen
def extraer_texto_ocr(path_archivo):
    extension = path_archivo.lower().split('.')[-1]

    if extension == 'pdf':
        try:
            imagenes = convert_from_path(path_archivo, dpi=200)
            texto = ""
            for img in imagenes:
                texto += pytesseract.image_to_string(img)
            return texto
        except Exception as e:
            print("OCR PDF:", e)
            return None
    else:
        try:
            img = cv2.imread(path_archivo)
            return pytesseract.image_to_string(img)
        except Exception as e:
            print("OCR imagen:", e)
            return None

# Procesa un archivo recibido para comprobar si corresponde a un presupuesto firmado ya generado. Si coincide, lo archiva y actualiza su estado en la base de datos
def procesar_archivo_firmado(path_local):
    texto = extraer_texto_ocr(path_local)
    if not texto:
        return None, "No se pudo extraer texto"

    presupuestos = obtener_documentos("presupuestos", "revisado")
    for p in presupuestos:
        if str(p["id_trabajo"]) in texto or (p["descripcion"] and p["descripcion"].lower() in texto.lower()):
            nuevo_nombre = f"Firmado_{p['id_trabajo']}.pdf"
            destino_relativo = f"Data/Presupuestos/Firmado/{nuevo_nombre}"
            destino_absoluto = os.path.join("Scripts", destino_relativo)

            os.makedirs(os.path.dirname(destino_absoluto), exist_ok=True)
            shutil.move(path_local, destino_absoluto)

            marcar_presupuesto_como_firmado(p["id_trabajo"], destino_relativo)
            return p["id_trabajo"], None

    return None, "No se encontró presupuesto coincidente"
