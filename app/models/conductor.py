from datetime import date, datetime

from app import db


class Conductor(db.Model):
    __tablename__ = "conductores"

    id_conductor = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    num_licencia = db.Column(db.String(50), unique=True, nullable=False)
    fecha_vencimiento_lic = db.Column(db.Date, nullable=False)
    contacto_emergencia = db.Column(db.String(120), nullable=False)
    tel_emergencia = db.Column(db.String(20), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_registro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def licencia_vigente(self):
        return self.fecha_vencimiento_lic >= date.today()
