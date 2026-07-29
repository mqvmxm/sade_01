# Blueprint de emergencias (RF-4): aviso silencioso y discreto activado por
# el conductor, no un botón de pánico prominente — el motor asíncrono de
# APScheduler (RF-3.4/3.5) ya cubre la detección automática de retrasos.
# Este endpoint es el disparo manual explícito ante una emergencia real.

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app import db
from app.controllers.conductor import conductor_required
from app.models.alerta import Alerta
from app.models.bitacora import Bitacora
from app.models.emergencia import Emergencia
from app.models.viaje import Viaje
from app.services.notificaciones import (
    enviar_sms,
    enviar_whatsapp,
    generar_mensaje_emergencia,
)

emergencia = Blueprint("emergencia", __name__)


@emergencia.route("/activar", methods=["POST"])
@conductor_required
def activar():
    """Registra una emergencia disparada por el conductor (RF-4.1/4.2/4.6) y
    dispara las notificaciones de WhatsApp/SMS (RF-4.3/4.4/4.5).

    Responde JSON porque el frontend lo llama con fetch(), no como un
    formulario tradicional.
    """
    perfil = current_user.conductor
    if perfil is None:
        return (
            jsonify({"ok": False, "error": "Tu cuenta no tiene un perfil de conductor asociado."}),
            403,
        )

    viaje = Viaje.query.filter(
        Viaje.id_conductor == perfil.id_conductor,
        Viaje.estado.in_(["activo", "alerta"]),
    ).first()
    if viaje is None:
        return jsonify({"ok": False, "error": "No tienes un viaje en curso."}), 400

    # latitud/longitud son opcionales: si el navegador no pudo obtener la
    # ubicación (permiso denegado, timeout, sin soporte), el frontend manda
    # el aviso igual mandandolos vacíos, y aquí se guardan como NULL en vez
    # de rechazar la emergencia — perder la ubicación nunca debe impedir
    # registrar y notificar el aviso.
    latitud_texto = request.form.get("latitud", "").strip()
    longitud_texto = request.form.get("longitud", "").strip()

    if latitud_texto or longitud_texto:
        try:
            latitud = float(latitud_texto)
            longitud = float(longitud_texto)
        except ValueError:
            return jsonify({"ok": False, "error": "Coordenadas GPS inválidas."}), 400
    else:
        latitud = None
        longitud = None

    registro_emergencia = Emergencia(
        id_viaje=viaje.id_viaje,
        id_conductor=perfil.id_conductor,
        latitud=latitud,
        longitud=longitud,
        estado_envio_ws="pendiente",
        estado_envio_sms="pendiente",
        enviado_offline=False,
    )
    db.session.add(registro_emergencia)

    viaje.estado = "emergencia"

    ubicacion_texto = (
        f"({latitud}, {longitud})" if latitud is not None else "ubicación no disponible"
    )
    alerta = Alerta(
        id_viaje=viaje.id_viaje,
        id_conductor=perfil.id_conductor,
        tipo="panico",
        prioridad=1,
        mensaje=f"Emergencia activada por {perfil.nombre} en {ubicacion_texto}.",
        atendida=False,
    )
    db.session.add(alerta)

    # La Emergencia queda guardada aquí, antes de intentar notificar. Si el
    # envío de WhatsApp/SMS falla más abajo, el registro del evento ya está
    # a salvo: solo se pierde la notificación, nunca el hecho de que ocurrió.
    db.session.commit()

    _notificar_emergencia(registro_emergencia, perfil)

    return jsonify({"ok": True})


def _notificar_emergencia(registro_emergencia, perfil):
    """Envía WhatsApp y SMS al contacto de emergencia del conductor y al
    administrador (RF-4.3/4.4), y deja constancia en Emergencia y Bitacora.

    Un fallo aquí nunca debe tumbar el request que ya respondió: cualquier
    excepción no prevista se atrapa y solo revierte los cambios de estado de
    esta función (el registro de Emergencia ya fue confirmado antes).
    """
    try:
        mensaje = generar_mensaje_emergencia(
            perfil.nombre, registro_emergencia.latitud, registro_emergencia.longitud
        )
        numero_conductor = perfil.tel_emergencia
        numero_admin = current_app.config.get("ADMIN_PHONE_NUMBER", "")

        exito_ws_conductor, error_ws_conductor = enviar_whatsapp(numero_conductor, mensaje)
        exito_ws_admin, error_ws_admin = enviar_whatsapp(numero_admin, mensaje)
        exito_sms_conductor, error_sms_conductor = enviar_sms(numero_conductor, mensaje)
        exito_sms_admin, error_sms_admin = enviar_sms(numero_admin, mensaje)

        # WhatsApp y SMS se evalúan de forma independiente: 'enviado' solo si
        # AMBOS destinatarios de ese canal recibieron el mensaje.
        registro_emergencia.estado_envio_ws = (
            "enviado" if exito_ws_conductor and exito_ws_admin else "fallido"
        )
        registro_emergencia.estado_envio_sms = (
            "enviado" if exito_sms_conductor and exito_sms_admin else "fallido"
        )

        _registrar_bitacora_envio(registro_emergencia, "WhatsApp", "contacto de emergencia", exito_ws_conductor, error_ws_conductor)
        _registrar_bitacora_envio(registro_emergencia, "WhatsApp", "administrador", exito_ws_admin, error_ws_admin)
        _registrar_bitacora_envio(registro_emergencia, "SMS", "contacto de emergencia", exito_sms_conductor, error_sms_conductor)
        _registrar_bitacora_envio(registro_emergencia, "SMS", "administrador", exito_sms_admin, error_sms_admin)

        db.session.commit()
    except Exception as error:
        db.session.rollback()
        print(f"[emergencia] Error al enviar notificaciones: {error}")


def _registrar_bitacora_envio(registro_emergencia, canal, destinatario, exito, error):
    """Agrega una fila de Bitacora describiendo un intento de envío individual."""
    resultado = "enviado" if exito else f"fallido ({error})" if error else "fallido"
    bitacora = Bitacora(
        id_usuario=current_user.id_usuario,
        accion="envio_notificacion_emergencia",
        descripcion=f"{canal} a {destinatario}: {resultado}.",
        tabla_afectada="emergencias",
        registro_id=registro_emergencia.id_emergencia,
    )
    db.session.add(bitacora)
