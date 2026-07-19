from datetime import datetime

from sqlalchemy import CheckConstraint

from app import db


class Vehiculo(db.Model):
    __tablename__ = "vehiculos"

    id_vehiculo = db.Column(db.Integer, primary_key=True)
    placas = db.Column(db.String(20), unique=True, nullable=False)
    num_unidad = db.Column(db.String(20), nullable=False)
    marca = db.Column(db.String(80), nullable=False)
    modelo = db.Column(db.String(80), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    num_serie = db.Column(db.String(50), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="disponible")
    ultima_actualizacion = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "estado IN ('disponible', 'en_ruta', 'en_taller')",
            name="ck_vehiculos_estado",
        ),
    )
