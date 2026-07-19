from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import CheckConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class Usuario(db.Model, UserMixin):
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
    fecha_registro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conductor = db.relationship("Conductor", backref=db.backref("usuarios", lazy=True))

    __table_args__ = (
        CheckConstraint(
            "rol IN ('admin', 'conductor', 'mecanico')", name="ck_usuarios_rol"
        ),
    )

    def get_id(self):
        return str(self.id_usuario)

    def set_password(self, password):
        self.contrasena = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.contrasena, password)

    def es_admin(self):
        return self.rol == "admin"

    def es_conductor(self):
        return self.rol == "conductor"

    def es_mecanico(self):
        return self.rol == "mecanico"
