import json
from Scripts.generador_factura import generar_factura, ConfiguracionFactura
from Scripts.bbdd import (asociar_trabajo_a_cliente, insertar_factura, obtener_id_cliente_por_remitente)

# Genera automáticamente una factura a partir de un presupuesto aprobado, vinculando cliente y trabajo, y guardando el resultado en la base de datos
def generar_borrador_factura_automatico(cliente, presupuesto):
    id_cliente = cliente.get("id_cliente") if cliente else None

    if not id_cliente:
        canal = presupuesto.get("canal")
        remitente = presupuesto.get("identificador_cliente") or presupuesto.get("remitente")
        id_cliente = obtener_id_cliente_por_remitente(remitente, canal)

    if not id_cliente:
        return

    id_trabajo = presupuesto["id_trabajo"]
    asociar_trabajo_a_cliente(id_cliente, id_trabajo)

    conceptos_raw = presupuesto["conceptos"]
    conceptos = json.loads(conceptos_raw) if isinstance(conceptos_raw, str) else conceptos_raw

    condiciones_presupuesto = presupuesto.get("condiciones", "")
    texto_pago = ConfiguracionFactura().texto_pago
    condiciones = (condiciones_presupuesto.strip() + "\n\n" + texto_pago.strip()).strip() 
    descripcion = presupuesto.get("descripcion", "") 
    canal = presupuesto.get("canal")
    identificador_cliente = presupuesto.get("identificador_cliente")

    pedido = {
        "id_cliente": id_cliente,
        "descripcion": descripcion,
        "conceptos": conceptos,
        "informacion_adicional": condiciones
    }

    config = ConfiguracionFactura()

    ruta_docx, ruta_pdf, _ = generar_factura(pedido, config, id_trabajo)

    insertar_factura(
        id_cliente=id_cliente,
        id_trabajo=id_trabajo,
        ruta_documento=ruta_pdf,
        ruta_word=ruta_docx,
        estado="pendiente",
        canal=canal,
        identificador_cliente=identificador_cliente,
        descripcion=descripcion,
        conceptos=conceptos,
        informacion_adicional=condiciones
    )
    return {
        "ruta_word": ruta_docx,
        "ruta_pdf": ruta_pdf,
        "id_trabajo": id_trabajo
    }