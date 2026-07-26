# Blueprint de emergencias (RF-4): aviso silencioso y discreto activado por
# el conductor, no un botón de pánico prominente — el motor asíncrono de
# APScheduler (RF-3.4/3.5) ya cubre la detección automática de retrasos.
# Este endpoint es el disparo manual explícito ante una emergencia real.

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app import db
from app.controllers.conductor import conductor_required
from app.models.alerta import Alerta
from app.models.emergencia import Emergencia
from app.models.viaje import Viaje

emergencia = Blueprint("emergencia", __name__)


@emergencia.route("/activar", methods=["POST"])
@conductor_required
def activar():
    """Registra una emergencia disparada por el conductor (RF-4.1/4.2/4.6).

    Twilio (WhatsApp/SMS, RF-4.3/4.4) todavía no está integrado aquí: los
    campos de estado de envío quedan en 'pendiente' hasta el siguiente paso.
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

    try:
        latitud = float(request.form.get("latitud", ""))
        longitud = float(request.form.get("longitud", ""))
    except ValueError:
        return jsonify({"ok": False, "error": "Coordenadas GPS inválidas."}), 400

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

    alerta = Alerta(
        id_viaje=viaje.id_viaje,
        id_conductor=perfil.id_conductor,
        tipo="panico",
        prioridad=1,
        mensaje=(
            f"Emergencia activada por {perfil.nombre} en "
            f"({latitud}, {longitud})."
        ),
        atendida=False,
    )
    db.session.add(alerta)

    db.session.commit()

    return jsonify({"ok": True})
