# Servicio de notificaciones de emergencia por WhatsApp y SMS vía Twilio
# (RF-4.3: WhatsApp; RF-4.4: SMS de respaldo; RF-4.5: mensaje con ubicación).
# Con SIMULATE_TWILIO=True (default, ver config.py) no se llama a la API
# real: solo se imprime el envío simulado, para poder desarrollar y probar
# el flujo completo sin credenciales de Twilio. La simulación reemplaza
# únicamente la llamada al canal (WhatsApp/SMS), nunca la validación del
# número de destino: un número vacío o inválido debe fallar igual en modo
# simulado que en modo real.

import re

from flask import current_app
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client


def normalizar_numero(numero):
    """Normaliza un número de teléfono mexicano a formato E.164 (+52...).

    Acepta números con o sin lada de país, con espacios, guiones o
    paréntesis. No agrega el prefijo 'whatsapp:' — eso lo hace
    enviar_whatsapp() únicamente para ese canal.

    Devuelve None (no lanza excepción) si `numero` es None, cadena vacía, o
    no tiene exactamente 10 dígitos de número local mexicano después de
    limpiar todo lo que no sea dígito y quitar la lada de país si venía
    incluida. Se eligió None en vez de una excepción porque
    enviar_whatsapp()/enviar_sms() ya reportan sus fallas como tupla
    (exito, error), y así todo el módulo usa un solo mecanismo de error.
    """
    if not numero:
        return None

    solo_digitos = re.sub(r"\D", "", numero)

    if len(solo_digitos) == 12 and solo_digitos.startswith("52"):
        solo_digitos = solo_digitos[2:]
    elif len(solo_digitos) == 13 and solo_digitos.startswith("521"):
        solo_digitos = solo_digitos[3:]

    if len(solo_digitos) != 10:
        return None

    return f"+52{solo_digitos}"


def generar_mensaje_emergencia(nombre_conductor, latitud, longitud):
    """Arma el texto de la notificación: conductor, tipo de aviso y ubicación (RF-4.5)."""
    link_mapa = f"https://maps.google.com/?q={latitud},{longitud}"
    return (
        f"[S.A.D.E.] Aviso silencioso activado por {nombre_conductor}. "
        f"Ubicación: {link_mapa}"
    )


def _simulacion_activa():
    return current_app.config.get("SIMULATE_TWILIO", True)


def _cliente_twilio():
    account_sid = current_app.config.get("TWILIO_ACCOUNT_SID", "")
    auth_token = current_app.config.get("TWILIO_AUTH_TOKEN", "")
    return Client(account_sid, auth_token)


def enviar_whatsapp(numero_destino, mensaje):
    """Envía un WhatsApp vía Twilio (RF-4.3).

    Devuelve (exito: bool, error: str | None). El número se valida ANTES de
    decidir si simular o llamar a la API real: si normalizar_numero()
    devuelve None, la función falla con "número inválido o no configurado"
    sin importar el valor de SIMULATE_TWILIO. En modo simulado (con número
    válido) siempre devuelve éxito sin llamar a la API real.
    """
    numero_e164 = normalizar_numero(numero_destino)
    if numero_e164 is None:
        return False, "número inválido o no configurado"

    destino = f"whatsapp:{numero_e164}"

    if _simulacion_activa():
        print(f"[SIMULADO][WhatsApp] Para {destino}: {mensaje}")
        return True, None

    remitente = current_app.config.get("TWILIO_WHATSAPP_FROM", "")
    try:
        _cliente_twilio().messages.create(from_=remitente, to=destino, body=mensaje)
        return True, None
    except TwilioRestException as error:
        return False, str(error)


def enviar_sms(numero_destino, mensaje):
    """Envía un SMS de respaldo vía Twilio (RF-4.4).

    Devuelve (exito: bool, error: str | None). El número se valida ANTES de
    decidir si simular o llamar a la API real: si normalizar_numero()
    devuelve None, la función falla con "número inválido o no configurado"
    sin importar el valor de SIMULATE_TWILIO. En modo simulado (con número
    válido) siempre devuelve éxito sin llamar a la API real.
    """
    numero_e164 = normalizar_numero(numero_destino)
    if numero_e164 is None:
        return False, "número inválido o no configurado"

    if _simulacion_activa():
        print(f"[SIMULADO][SMS] Para {numero_e164}: {mensaje}")
        return True, None

    remitente = current_app.config.get("TWILIO_SMS_FROM", "")
    try:
        _cliente_twilio().messages.create(from_=remitente, to=numero_e164, body=mensaje)
        return True, None
    except TwilioRestException as error:
        return False, str(error)
