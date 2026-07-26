# Application factory de S.A.D.E.: crea y configura la instancia de Flask,
# inicializa las extensiones (SQLAlchemy, Flask-Login) y registra un
# blueprint por rol/área funcional (auth, admin, conductor, mecánico,
# emergencia). Soporta RF-1 (autenticación y accesos) a nivel de arranque.

import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
scheduler = BackgroundScheduler()


def create_app(config_class=Config):
    """Construye la app Flask: configuración, extensiones y blueprints.

    Usa el patrón application factory para poder crear instancias distintas
    (por ejemplo con otra configuración) sin depender de un objeto global.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from app import models  # noqa: F401

    from app.models.usuario import Usuario

    @login_manager.user_loader
    def load_user(id_usuario):
        """Recupera el Usuario de la sesión activa (requerido por Flask-Login)."""
        return Usuario.query.get(int(id_usuario))

    from app.controllers.auth import auth as auth_bp
    app.register_blueprint(auth_bp)

    from app.controllers.admin import admin as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.controllers.conductor import conductor as conductor_bp
    app.register_blueprint(conductor_bp, url_prefix='/conductor')

    from app.controllers.mecanico import mecanico as mecanico_bp
    app.register_blueprint(mecanico_bp, url_prefix='/mecanico')

    from app.controllers.emergencia import emergencia as emergencia_bp
    app.register_blueprint(emergencia_bp, url_prefix='/emergencia')

    _iniciar_scheduler(app)

    return app


def _iniciar_scheduler(app):
    """Agenda revisar_viajes_activos() cada 60s (RF-3.4).

    En modo debug, el reloader de Flask relanza el proceso completo en un
    subproceso hijo; sin este chequeo, create_app() correría dos veces y
    duplicaría el job. WERKZEUG_RUN_MAIN solo está presente ('true') en el
    subproceso hijo real, así que el proceso monitor se salta el arranque.
    scheduler.running evita además un segundo job si create_app() se llama
    más de una vez dentro del mismo proceso.
    """
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    if scheduler.running:
        return

    from app.controllers.scheduler import revisar_viajes_activos

    def _revisar_viajes_activos_job():
        with app.app_context():
            revisar_viajes_activos()

    scheduler.add_job(
        _revisar_viajes_activos_job,
        "interval",
        seconds=60,
        id="revisar_viajes_activos",
    )
    scheduler.start()
