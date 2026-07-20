# Blueprint de emergencias (RF-4). El endpoint de pánico es un stub: falta
# capturar GPS (RF-4.2), notificar por WhatsApp/Twilio (RF-4.3) y SMS de
# respaldo (RF-4.4), y registrar el evento en BD (RF-4.6).

from flask import Blueprint
from flask_login import login_required

emergencia = Blueprint("emergencia", __name__)


@emergencia.route("/panico")
@login_required
def panico():
    """Endpoint del botón de pánico (RF-4.1); pendiente de implementación."""
    return "Módulo de emergencias — pendiente de implementar"
