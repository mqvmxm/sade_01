# Motor asíncrono de monitoreo de rutas (RF-3.4: chequeo periódico con
# APScheduler cada 60s; RF-3.5: alerta automática cuando un conductor supera
# su ETA sin confirmar llegada). El job se agenda en app/__init__.py.

from datetime import datetime

from app import db
from app.models.alerta import Alerta
from app.models.viaje import Viaje


def revisar_viajes_activos():
    """Genera una Alerta de retraso para cada Viaje 'activo' que ya superó su ETA.

    Se ejecuta periódicamente fuera de una petición HTTP (ver
    app/__init__.py), por lo que quien la agenda es responsable de envolver
    la llamada en un app.app_context(). No duplica alertas: si el viaje ya
    tiene una Alerta tipo='retraso', se ignora en las siguientes corridas.
    """
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

        db.session.commit()
    except Exception as error:
        db.session.rollback()
        print(f"[scheduler] Error al revisar viajes activos: {error}")
