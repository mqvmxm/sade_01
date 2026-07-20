# Modelo de reportes de avería registrados por el mecánico sobre un
# vehículo/viaje (RF-5: Estado vehicular).

from datetime import datetime

from sqlalchemy import CheckConstraint

from app import db


class ReporteAveria(db.Model):
    """Reporte de avería de un vehículo, vinculado al viaje en curso (RF-5.3).

    `estado_vehiculo_prev` conserva el estado del vehículo justo antes
    del reporte, útil para auditoría del cambio a 'en_taller' (RF-5.2).
    """

    __tablename__ = "reportes_averia"

    id_reporte = db.Column(db.Integer, primary_key=True)
    id_viaje = db.Column(db.Integer, db.ForeignKey("viajes.id_viaje"), nullable=False)
    id_vehiculo = db.Column(
        db.Integer, db.ForeignKey("vehiculos.id_vehiculo"), nullable=False
    )
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuarios.id_usuario"), nullable=False
    )
    descripcion = db.Column(db.Text, nullable=False)
    estado_vehiculo_prev = db.Column(db.String(20), nullable=False)
    registrado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    viaje = db.relationship("Viaje", backref=db.backref("reportes_averia", lazy=True))
    vehiculo = db.relationship(
        "Vehiculo", backref=db.backref("reportes_averia", lazy=True)
    )
    usuario = db.relationship(
        "Usuario", backref=db.backref("reportes_averia", lazy=True)
    )

    __table_args__ = (
        CheckConstraint(
            "estado_vehiculo_prev IN ('disponible', 'en_ruta', 'en_taller')",
            name="ck_reportes_averia_estado_vehiculo_prev",
        ),
    )
