import requests

# Utiliza el servicio Nominatim de OpenStreetMap para obtener las coordenadas geográficas de una dirección postal
def get_coordinates(direccion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": direccion,
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "KlariaApp"}

    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200 and response.json():
        data = response.json()[0]
        return float(data["lat"]), float(data["lon"])
    else:
        return None, None

# Calcula la duración aproximada en minutos de una ruta en coche entre dos coordenadas usando el servicio OSRM
def get_route_duration(origen, destino):
    if None in origen or None in destino:
        return None

    lat1, lon1 = origen
    lat2, lon2 = destino
    url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"

    response = requests.get(url)
    if response.status_code == 200 and "routes" in response.json():
        duracion_seg = response.json()["routes"][0]["duration"]
        return int(duracion_seg / 60)  # minutos
    else:
        return None

# Busca los primeros huecos disponibles para un trabajo concreto, teniendo en cuenta eventos ya registrados y tiempos de desplazamiento
def buscar_huecos_disponibles(id_trabajo, duracion_minutos):
    from Scripts.bbdd import obtener_presupuesto_por_id_trabajo, obtener_cliente_por_id, obtener_horarios_semana
    from datetime import datetime, timedelta

    presupuesto = obtener_presupuesto_por_id_trabajo(id_trabajo)
    if not presupuesto:
        print("No se encontró el presupuesto.")
        return []

    id_cliente = presupuesto["id_cliente"]
    cliente = obtener_cliente_por_id(id_cliente)

    direccion_nueva = cliente.get("direccion", "")
    poblacion = cliente.get("poblacion", "")
    provincia = cliente.get("provincia", "")

    direccion_completa = f"{direccion_nueva}, {poblacion}, {provincia}".strip(", ")
    coordenadas_nueva = get_coordinates(direccion_completa)

    fecha_base = datetime.today() + timedelta(days=3)
    resultados = []
    bloques_necesarios = duracion_minutos // 15 + (1 if duracion_minutos % 15 else 0)

    for dia in range(7):
        dia_actual = fecha_base + timedelta(days=dia)
        fecha_str = dia_actual.strftime("%Y-%m-%d")

        eventos = obtener_horarios_semana(fecha_str, poblacion)
        eventos = sorted(eventos, key=lambda e: e["hora"])

        ocupados_bloques = [False] * 52  # de 08:00 a 21:00

        for ev in eventos:
            h, m = map(int, ev["hora"].split(":"))
            inicio = ((h - 8) * 4) + (m // 15)
            duracion_evento = (ev["duracion"] + 14) // 15

            # Calcular duración de desplazamiento desde el evento a la nueva dirección
            direccion_evento = ev["direccion"] + ", " + ev["poblacion"]
            coord_evento = get_coordinates(direccion_evento)

            desplazamiento_min = get_route_duration(coord_evento, coordenadas_nueva)
            if desplazamiento_min is None:
                desplazamiento_min = 0

            bloques_extra = (desplazamiento_min + 14) // 15
            for i in range(max(0, inicio - bloques_extra), min(inicio + duracion_evento + bloques_extra, 52)):
                ocupados_bloques[i] = True

        # Buscar huecos libres teniendo en cuenta desplazamientos
        candidatos = []
        for i in range(0, 52 - bloques_necesarios + 1):
            if all(not ocupado for ocupado in ocupados_bloques[i:i + bloques_necesarios]):
                antes = ocupados_bloques[i - 1] if i > 0 else False
                despues = ocupados_bloques[i + bloques_necesarios] if i + bloques_necesarios < 52 else False
                pegado = antes or despues
                candidatos.append((i, pegado))

        # Orden: huecos pegados primero
        candidatos.sort(key=lambda x: (not x[1], x[0]))

        for i, _ in candidatos:
            hora = 8 * 60 + i * 15
            hora_real = dia_actual.replace(hour=hora // 60, minute=hora % 60, second=0, microsecond=0)
            hora_str = hora_real.strftime("%Y-%m-%dT%H:%M")
            resultados.append(hora_str)
            if len(resultados) >= 5:
                return resultados

    if not resultados:
        print("No se encontraron huecos disponibles.")
    return resultados