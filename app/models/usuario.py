# Modelo de cuentas de acceso al sistema (RF-1: Autenticación y accesos).
# Cada Usuario tiene un rol fijo (admin/conductor/mecanico) que determina a
# qué dashboards y acciones puede acceder.

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import CheckConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class Usuario(db.Model, UserMixin):
    """Cuenta de acceso al sistema, vinculada a RF-1.1 (registro por rol).

    Si el rol es 'conductor', id_conductor enlaza con su perfil en la
    tabla conductores (licencia, contacto de emergencia, etc.).
    """

    __tablename__ = "usuarios"

    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    nombre_usuario = db.Column(db.String(80), unique=True, nullable=False)
    contrasena = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    id_conductor = db.Column(
        db.Integer, db.ForeignKey("conductores.id_conductor"), nullable=True
    )
    fecha_registro = db.Column(db.DateTime, nullable=False, default=datetime.now)

    conductor = db.relationship("Conductor", backref=db.backref("usuarios", lazy=True))

    __table_args__ = (
        CheckConstraint(
            "rol IN ('admin', 'conductor', 'mecanico')", name="ck_usuarios_rol"
        ),
    )

    def get_id(self):
        """Devuelve el identificador que Flask-Login guarda en la sesión."""
        return str(self.id_usuario)

    def set_password(self, password):
        """Genera y guarda el hash de la contraseña (nunca se almacena en claro)."""
        self.contrasena = generate_password_hash(password)

    def check_password(self, password):
        """Valida credenciales de login comparando contra el hash guardado (RF-1.2)."""
        return check_password_hash(self.contrasena, password)

    def es_admin(self):
        """Indica si el usuario tiene rol administrador (control de autorización, RF-1.3)."""
        return self.rol == "admin"

    def es_conductor(self):
        """Indica si el usuario tiene rol conductor (control de autorización, RF-1.3)."""
        return self.rol == "conductor"

    def es_mecanico(self):
        """Indica si el usuario tiene rol mecánico (control de autorización, RF-1.3)."""
        return self.rol == "mecanico"
