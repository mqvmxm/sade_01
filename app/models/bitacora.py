# Modelo de bitácora de auditoría: no corresponde a ningún RF específico
# del documento de requisitos; se agregó como buena práctica de diseño de
# BD, ligada a RNF-02 (Seguridad) y RNF-07 (Mantenibilidad).

from datetime import datetime

from app import db


class Bitacora(db.Model):
    """Registro genérico de auditoría de acciones sobre el sistema.

    Cada fila referencia la tabla y el registro afectado
    (tabla_afectada + registro_id) en lugar de una FK específica, para
    poder trazar cambios sobre cualquier entidad desde un solo lugar.
    """

    __tablename__ = "bitacora"

    id_bitacora = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey("usuarios.id_usuario"), nullable=False
    )
    accion = db.Column(db.String(80), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    tabla_afectada = db.Column(db.String(80), nullable=False)
    registro_id = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)

    usuario = db.relationship("Usuario", backref=db.backref("bitacora", lazy=True))
