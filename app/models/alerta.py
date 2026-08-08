# Modelo de alertas generadas por el motor asíncrono de monitoreo
# (RF-3.4: chequeo periódico con APScheduler cada 60s; RF-3.5: alerta
# automática ante retraso, pánico o licencia vencida).

from datetime import datetime

from sqlalchemy import CheckConstraint

from app import db


class Alerta(db.Model):
    """Aviso ligado a un viaje/conductor con tipo, prioridad (1-3) y estado de atención.

    Generada automáticamente por el motor asíncrono (RF-3.4/RF-3.5) al
    detectar retraso, pánico o licencia vencida.
    """

    __tablename__ = "alertas"

    id_alerta = db.Column(db.Integer, primary_key=True)
    id_viaje = db.Column(db.Integer, db.ForeignKey("viajes.id_viaje"), nullable=False)
    id_conductor = db.Column(
        db.Integer, db.ForeignKey("conductores.id_conductor"), nullable=False
    )
    tipo = db.Column(db.String(20), nullable=False)
    prioridad = db.Column(db.Integer, nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    atendida = db.Column(db.Boolean, nullable=False, default=False)
    generada_en = db.Column(db.DateTime, nullable=False, default=datetime.now)
    atendida_en = db.Column(db.DateTime, nullable=True)
    # Estado intermedio, solo relevante para tipo='asistencia_mecanica': el
    # mecánico ya vio el aviso pero todavía no completa el reporte de avería
    # que la marca 'atendida' (ver mecanico.py, alertas_marcar_vista).
    vista = db.Column(db.Boolean, nullable=False, default=False)
    vista_en = db.Column(db.DateTime, nullable=True)

    viaje = db.relationship("Viaje", backref=db.backref("alertas", lazy=True))
    conductor = db.relationship("Conductor", backref=db.backref("alertas", lazy=True))

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('retraso', 'panico', 'licencia_vencida', 'asistencia_mecanica', "
            "'incidencia_trafico', 'ruta_no_iniciada')",
            name="ck_alertas_tipo",
        ),
        CheckConstraint("prioridad IN (1, 2, 3)", name="ck_alertas_prioridad"),
    )
