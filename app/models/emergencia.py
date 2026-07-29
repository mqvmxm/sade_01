# Modelo de emergencias activadas por el conductor (RF-4: Emergencias).
# Registra la ubicación GPS y el estado de envío por cada canal de
# notificación (WhatsApp vía Twilio y SMS de respaldo).

from datetime import datetime

from sqlalchemy import CheckConstraint

from app import db


class Emergencia(db.Model):
    """Evento de pánico disparado desde un viaje (RF-4.1: botón de pánico).

    Guarda las coordenadas GPS capturadas (RF-4.2), el timestamp
    (RF-4.6) y el estado de envío independiente para WhatsApp (RF-4.3)
    y SMS de respaldo (RF-4.4). `enviado_offline` marca los casos en los
    que la emergencia se registró sin conectividad inmediata.

    latitud/longitud son NULL cuando el conductor activó el aviso sin que
    el navegador pudiera obtener su ubicación (permiso denegado, GPS sin
    señal, timeout o dispositivo sin soporte de geolocalización): el aviso
    de emergencia igual debe registrarse y notificarse, solo que sin
    coordenadas (ver app/controllers/emergencia.py, activar()).
    """

    __tablename__ = "emergencias"

    id_emergencia = db.Column(db.Integer, primary_key=True)
    id_viaje = db.Column(db.Integer, db.ForeignKey("viajes.id_viaje"), nullable=False)
    id_conductor = db.Column(
        db.Integer, db.ForeignKey("conductores.id_conductor"), nullable=False
    )
    latitud = db.Column(db.Float, nullable=True)
    longitud = db.Column(db.Float, nullable=True)
    estado_envio_ws = db.Column(db.String(20), nullable=False, default="pendiente")
    estado_envio_sms = db.Column(db.String(20), nullable=False, default="pendiente")
    enviado_offline = db.Column(db.Boolean, nullable=False, default=False)
    activada_en = db.Column(db.DateTime, nullable=False, default=datetime.now)

    viaje = db.relationship("Viaje", backref=db.backref("emergencias", lazy=True))
    conductor = db.relationship("Conductor", backref=db.backref("emergencias", lazy=True))

    __table_args__ = (
        CheckConstraint(
            "estado_envio_ws IN ('pendiente', 'enviado', 'fallido')",
            name="ck_emergencias_estado_envio_ws",
        ),
        CheckConstraint(
            "estado_envio_sms IN ('pendiente', 'enviado', 'fallido')",
            name="ck_emergencias_estado_envio_sms",
        ),
    )
