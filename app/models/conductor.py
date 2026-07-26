# Modelo de perfil de conductor: datos de licencia y contacto de emergencia
# (RF-2: Gestión de flota). Es independiente de Usuario para que pueda existir
# un conductor registrado en la flota antes de tener cuenta de acceso.

from datetime import date, datetime

from app import db


class Conductor(db.Model):
    """Perfil de un conductor de la flota (RF-2.1: registro con contacto de emergencia)."""

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
        """Compara la fecha de vencimiento de la licencia contra la fecha actual (RF-6.1).

        Usado para bloquear el check-in de viajes cuando la licencia está
        vencida (RF-6.2).
        """
        return self.fecha_vencimiento_lic >= date.today()

    def licencia_proxima_a_vencer(self, dias=30):
        """Indica si la licencia sigue vigente pero vence dentro de los próximos `dias` días."""
        if not self.licencia_vigente():
            return False
        return (self.fecha_vencimiento_lic - date.today()).days <= dias
