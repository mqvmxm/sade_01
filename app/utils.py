# Validaciones de formulario compartidas entre los distintos flujos que
# crean un Viaje: la programación de rutas del admin
# (admin.viajes_programar) y, antes de RF-3.7, el check-in del conductor.

from datetime import datetime, timedelta


def validar_datos_viaje(origen, destino, eta_texto):
    """Valida origen, destino y ETA de un viaje nuevo.

    Retorna (origen, destino, eta, error). Si error es None, origen/destino
    vienen ya recortados de espacios y eta es un datetime válido con al
    menos 10 minutos de margen sobre la hora del servidor; si error no es
    None, origen/destino/eta son None y error trae el mensaje a mostrar.
    """
    origen = (origen or "").strip()
    destino = (destino or "").strip()
    if not origen or not destino:
        return None, None, None, "Debes indicar origen y destino."

    if len(origen) < 3 or len(destino) < 3:
        return None, None, None, "Origen y destino deben tener al menos 3 caracteres."

    if origen.isdigit() or destino.isdigit():
        return None, None, None, "Origen y destino deben ser un nombre de lugar válido, no solo números."

    # Insensible a mayúsculas y a diferencias de espaciado (" La  Paz " vs
    # "la paz" deben contarse como el mismo lugar).
    if " ".join(origen.split()).casefold() == " ".join(destino.split()).casefold():
        return None, None, None, "Origen y destino no pueden ser el mismo lugar."

    try:
        eta = datetime.strptime(eta_texto or "", "%Y-%m-%dT%H:%M")
    except ValueError:
        return None, None, None, "La hora estimada de llegada (ETA) no es válida."

    if eta < datetime.now() + timedelta(minutes=10):
        return (
            None,
            None,
            None,
            "La hora estimada de llegada debe ser al menos 10 minutos después de ahora.",
        )

    return origen, destino, eta, None
