from datetime import datetime

from app import db


class Bitacora(db.Model):
    __tablename__ = "bitacora"

    id_bitacora = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuarios.id_usuario"), nullable=False
    )
    accion = db.Column(db.String(80), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    tabla_afectada = db.Column(db.String(80), nullable=False)
    registro_id = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    usuario = db.relationship("Usuario", backref=db.backref("bitacora", lazy=True))
