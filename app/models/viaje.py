from datetime import datetime

from sqlalchemy import CheckConstraint

from app import db


class Viaje(db.Model):
    __tablename__ = "viajes"

    id_viaje = db.Column(db.Integer, primary_key=True)
    id_conductor = db.Column(
        db.Integer, db.ForeignKey("conductores.id_conductor"), nullable=False
    )
    id_vehiculo = db.Column(
        db.Integer, db.ForeignKey("vehiculos.id_vehiculo"), nullable=False
    )
    origen = db.Column(db.String(120), nullable=False)
    destino = db.Column(db.String(120), nullable=False)
    hora_salida = db.Column(db.DateTime, nullable=False)
    eta = db.Column(db.DateTime, nullable=False)
    hora_llegada = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.String(20), nullable=False, default="activo")
    fecha_registro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conductor = db.relationship("Conductor", backref=db.backref("viajes", lazy=True))
    vehiculo = db.relationship("Vehiculo", backref=db.backref("viajes", lazy=True))

    __table_args__ = (
        CheckConstraint(
            "estado IN ('activo', 'completado', 'alerta', 'emergencia', 'cerrado_admin')",
            name="ck_viajes_estado",
        ),
        # NOTA: la BD ya tiene un índice único parcial (idx_viaje_activo_unico)
        # que impide dos viajes 'activo' para el mismo id_vehiculo simultáneamente.
        # No se replica aquí en SQLAlchemy: la validación previa al INSERT se
        # hace en el controller (app/controllers/conductor.py, check-in).
    )
