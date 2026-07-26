# Modelo central de monitoreo de rutas: un viaje une un conductor con un
# vehículo entre un origen y un destino, con ETA y seguimiento de estado
# (RF-3: Monitoreo de rutas).

from datetime import datetime

from sqlalchemy import CheckConstraint

from app import db


class Viaje(db.Model):
    """Trayecto activo o histórico de un conductor con un vehículo (RF-3.1).

    hora_salida se registra al hacer check-in (RF-3.2) y hora_llegada al
    confirmar arribo (RF-3.3). El estado transiciona de 'activo' a
    'completado', o a 'alerta'/'emergencia' cuando el motor asíncrono
    (RF-3.4) detecta un retraso (RF-3.5) o se activa el botón de pánico.
    """

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
    fecha_registro = db.Column(db.DateTime, nullable=False, default=datetime.now)

    conductor = db.relationship("Conductor", backref=db.backref("viajes", lazy=True))
    vehiculo = db.relationship("Vehiculo", backref=db.backref("viajes", lazy=True))

    __table_args__ = (
        CheckConstraint(
            "estado IN ('activo', 'completado', 'alerta', 'emergencia', 'cerrado_admin')",
            name="ck_viajes_estado",
        ),
        # NOTA (RF-3.6, regla de integridad): la BD ya tiene un índice único
        # parcial (idx_viaje_activo_unico) que impide dos viajes 'activo' para
        # el mismo id_vehiculo simultáneamente (evita doble check-in del mismo
        # vehículo). No se replica aquí en SQLAlchemy: la validación previa al
        # INSERT se hace en el controller (app/controllers/conductor.py, check-in).
    )
