from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from app import models  # noqa: F401

    from app.models.usuario import Usuario

    @login_manager.user_loader
    def load_user(id_usuario):
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

    return app
