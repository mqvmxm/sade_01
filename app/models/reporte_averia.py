from datetime import datetime

from sqlalchemy import CheckConstraint

from app import db


class ReporteAveria(db.Model):
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
