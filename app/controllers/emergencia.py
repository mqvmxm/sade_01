from flask import Blueprint
from flask_login import login_required

emergencia = Blueprint("emergencia", __name__)


@emergencia.route("/panico")
@login_required
def panico():
    return "Módulo de emergencias — pendiente de implementar"
