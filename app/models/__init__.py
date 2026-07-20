# Agrega todos los modelos en un solo punto de importación para que
# SQLAlchemy los registre en el metadata antes de db.create_all()
# (ver app/__init__.py, que hace `from app import models`).

from app.models.usuario import Usuario
from app.models.conductor import Conductor
from app.models.vehiculo import Vehiculo
from app.models.viaje import Viaje
from app.models.alerta import Alerta
from app.models.emergencia import Emergencia
from app.models.reporte_averia import ReporteAveria
from app.models.bitacora import Bitacora
