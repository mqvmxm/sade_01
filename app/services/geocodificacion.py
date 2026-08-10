# Servicio de geocodificación inversa (coordenadas GPS -> dirección legible)
# para las incidencias que el conductor reporta con ubicación (ver
# conductor.reportar_incidencia). Usa la API pública de geocodificación
# inversa de Nominatim (OpenStreetMap), gratuita y sin API key, pero su
# política de uso exige identificar la aplicación con un header User-Agent:
# https://operations.osmfoundation.org/policies/nominatim/
#
# Mismo espíritu que app/services/notificaciones.py y correo.py: un fallo de
# este servicio (timeout, servicio caído, respuesta inválida) nunca debe
# impedir que se guarde lo que lo solicita -aquí, el reporte de incidencia
# del conductor-, así que obtener_direccion() nunca lanza, solo devuelve
# None.

import requests

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "SADE-ProyectoIntegrador/1.0"
_TIMEOUT_SEGUNDOS = 5


def obtener_direccion(latitud, longitud):
    """Geocodifica coordenadas GPS a una dirección legible (ej. "Blvd.
    Insurgentes, Tulancingo") vía la API de geocodificación inversa de
    Nominatim.

    Devuelve la dirección como texto (Nominatim la arma en el campo
    'display_name'), o None si latitud/longitud son None, o si la consulta
    falla por cualquier motivo (timeout, respuesta no válida, servicio
    caído, sin resultado). No lanza ninguna excepción.
    """
    if latitud is None or longitud is None:
        return None

    try:
        respuesta = requests.get(
            _NOMINATIM_URL,
            params={"lat": latitud, "lon": longitud, "format": "json"},
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT_SEGUNDOS,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (requests.RequestException, ValueError):
        return None

    if not isinstance(datos, dict):
        return None

    return datos.get("display_name") or None
