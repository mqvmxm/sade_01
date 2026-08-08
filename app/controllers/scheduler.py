# Motor asíncrono de monitoreo de rutas (RF-3.4: chequeo periódico con
# APScheduler cada 60s; RF-3.5: alerta automática cuando un conductor supera
# su ETA sin confirmar llegada). El job se agenda en app/__init__.py.

from datetime import datetime

from flask import current_app

from app import db
from app.models.alerta import Alerta
from app.models.bitacora import Bitacora
from app.models.usuario import Usuario
from app.models.viaje import Viaje
from app.services.notificaciones import (
    enviar_sms,
    enviar_whatsapp,
    generar_mensaje_retraso,
    quitar_codigos_ansi,
)


def revisar_viajes_activos():
    """Genera una Alerta de retraso para cada Viaje 'activo' que ya superó su ETA.

    Se ejecuta periódicamente fuera de una petición HTTP (ver
    app/__init__.py), por lo que quien la agenda es responsable de envolver
    la llamada en un app.app_context(). No duplica alertas: si el viaje ya
    tiene una Alerta tipo='retraso', se ignora en las siguientes corridas —
    y por lo tanto tampoco se reenvían las notificaciones de esa alerta
    (RF-3.5), que solo se disparan para alertas recién creadas en esta
    corrida.
    """
    alertas_nuevas = []

    try:
        ahora = datetime.now()
        viajes_activos = Viaje.query.filter_by(estado="activo").all()

        for viaje in viajes_activos:
            if ahora <= viaje.eta:
                continue

            ya_tiene_alerta_retraso = Alerta.query.filter_by(
                id_viaje=viaje.id_viaje, tipo="retraso"
            ).first()
            if ya_tiene_alerta_retraso is not None:
                continue

            alerta = Alerta(
                id_viaje=viaje.id_viaje,
                id_conductor=viaje.id_conductor,
                tipo="retraso",
                prioridad=2,
                mensaje=(
                    f"Conductor {viaje.conductor.nombre} superó su ETA "
                    "sin confirmar llegada."
                ),
                atendida=False,
            )
            db.session.add(alerta)
            viaje.estado = "alerta"
            alertas_nuevas.append((alerta, viaje))

        # La Alerta y el cambio de estado del viaje se confirman aquí, antes
        # de intentar notificar: es la parte crítica (RF-3.4/3.5) y debe
        # quedar a salvo aunque Twilio falle más abajo.
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        print(f"[scheduler] Error al revisar viajes activos: {error}")
        return

    for alerta, viaje in alertas_nuevas:
        _notificar_retraso(alerta, viaje)


def revisar_rutas_no_iniciadas():
    """Genera una Alerta informativa para cada Viaje 'programado' cuya ETA ya
    pasó sin que el conductor la haya iniciado (antes esto quedaba invisible
    para siempre).

    A diferencia de revisar_viajes_activos() (retraso de una ruta YA en
    curso), esta alerta es puramente informativa: el viaje ni siquiera
    arrancó, no hay conductor en ruta al que avisar por WhatsApp/SMS, así
    que NO llama a enviar_whatsapp/enviar_sms ni cambia viaje.estado (se
    queda en 'programado'; ver admin.viajes_programadas para el indicador
    visual inmediato en la tabla). No duplica alertas: si el viaje ya tiene
    una Alerta tipo='ruta_no_iniciada', se ignora en las siguientes corridas.

    Una vez creada, la ÚNICA vía de resolución es que el admin cancele la
    ruta (admin.viajes_cancelar_programada): conductor.viajes_iniciar
    rechaza de forma permanente iniciar cualquier ruta cuya ETA ya pasó, así
    que el inicio tardío ya no es (ni puede volver a ser) un camino de
    resolución.
    """
    try:
        ahora = datetime.now()
        rutas_programadas = Viaje.query.filter_by(estado="programado").all()

        for viaje in rutas_programadas:
            if ahora <= viaje.eta:
                continue

            ya_tiene_alerta = Alerta.query.filter_by(
                id_viaje=viaje.id_viaje, tipo="ruta_no_iniciada"
            ).first()
            if ya_tiene_alerta is not None:
                continue

            alerta = Alerta(
                id_viaje=viaje.id_viaje,
                id_conductor=viaje.id_conductor,
                tipo="ruta_no_iniciada",
                prioridad=2,
                mensaje=(
                    f"{viaje.conductor.nombre} no inició la ruta "
                    f"{viaje.origen} → {viaje.destino}, programada con ETA "
                    f"{viaje.eta.strftime('%d/%m/%Y %H:%M')}."
                ),
                atendida=False,
            )
            db.session.add(alerta)

        db.session.commit()
    except Exception as error:
        db.session.rollback()
        print(f"[scheduler] Error al revisar rutas no iniciadas: {error}")


def _notificar_retraso(alerta, viaje):
    """Envía WhatsApp y SMS al contacto de emergencia del conductor y al
    administrador (RF-3.5), y deja constancia en Bitácora.

    Va en su propio try/except porque el scheduler corre fuera de un
    request: un fallo de Twilio (o de cualquier otra cosa) aquí nunca debe
    tumbar el motor de monitoreo, que es la funcionalidad central del
    sistema. La Alerta y el estado 'alerta' del viaje ya quedaron
    confirmados en revisar_viajes_activos() antes de llamar esta función.
    """
    try:
        conductor = viaje.conductor
        mensaje = generar_mensaje_retraso(
            conductor.nombre, viaje.origen, viaje.destino, viaje.eta
        )
        numero_conductor = conductor.tel_emergencia
        numero_admin = current_app.config.get("ADMIN_PHONE_NUMBER", "")

        exito_ws_conductor, error_ws_conductor = enviar_whatsapp(numero_conductor, mensaje)
        exito_ws_admin, error_ws_admin = enviar_whatsapp(numero_admin, mensaje)
        exito_sms_conductor, error_sms_conductor = enviar_sms(numero_conductor, mensaje)
        exito_sms_admin, error_sms_admin = enviar_sms(numero_admin, mensaje)

        # El scheduler no corre dentro de un request: no hay current_user.
        # Bitacora.id_usuario es NOT NULL, así que se usa la cuenta de
        # acceso vinculada al conductor del viaje. Si el conductor no tiene
        # cuenta de usuario asociada, se omite el registro de Bitácora en
        # vez de fallar — la notificación en sí ya se intentó y no debe
        # perderse por un dato de auditoría faltante.
        usuario_conductor = Usuario.query.filter_by(
            id_conductor=viaje.id_conductor
        ).first()
        if usuario_conductor is not None:
            _registrar_bitacora_retraso(usuario_conductor, alerta, "WhatsApp", "contacto de emergencia", exito_ws_conductor, error_ws_conductor)
            _registrar_bitacora_retraso(usuario_conductor, alerta, "WhatsApp", "administrador", exito_ws_admin, error_ws_admin)
            _registrar_bitacora_retraso(usuario_conductor, alerta, "SMS", "contacto de emergencia", exito_sms_conductor, error_sms_conductor)
            _registrar_bitacora_retraso(usuario_conductor, alerta, "SMS", "administrador", exito_sms_admin, error_sms_admin)

        db.session.commit()
    except Exception as error:
        db.session.rollback()
        print(f"[scheduler] Error al notificar retraso del viaje {viaje.id_viaje}: {error}")


def _registrar_bitacora_retraso(usuario, alerta, canal, destinatario, exito, error):
    """Agrega una fila de Bitácora describiendo un intento de envío individual."""
    error_limpio = quitar_codigos_ansi(error)
    resultado = "enviado" if exito else f"fallido ({error_limpio})" if error_limpio else "fallido"
    bitacora = Bitacora(
        id_usuario=usuario.id_usuario,
        accion="envio_notificacion_retraso",
        descripcion=f"{canal} a {destinatario}: {resultado}.",
        tabla_afectada="alertas",
        registro_id=alerta.id_alerta,
    )
    db.session.add(bitacora)
