# Application factory de S.A.D.E.: crea y configura la instancia de Flask,
# inicializa las extensiones (SQLAlchemy, Flask-Login) y registra un
# blueprint por rol/área funcional (auth, admin, conductor, mecánico,
# emergencia). Soporta RF-1 (autenticación y accesos) a nivel de arranque.

import os

import click
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, flash, jsonify, redirect, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
scheduler = BackgroundScheduler()
csrf = CSRFProtect()


def create_app(config_class=Config):
    """Construye la app Flask: configuración, extensiones y blueprints.

    Usa el patrón application factory para poder crear instancias distintas
    (por ejemplo con otra configuración) sin depender de un objeto global.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

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

    _iniciar_scheduler(app)
    _registrar_cli(app)
    _registrar_manejadores_errores(app)

    return app


def _registrar_manejadores_errores(app):
    """Da un mensaje claro ante un token CSRF inválido/faltante (formulario
    expirado, sesión vencida, o solicitud manipulada) en vez de la página de
    error genérica de Werkzeug para un 400.

    /emergencia/activar se llama por fetch() y espera JSON, no una página
    HTML con flash + redirect: si ese endpoint tronara con la respuesta HTML
    genérica, el aviso silencioso se rompería en silencio (el frontend nunca
    vería el error). Se distingue por prefijo de ruta para responder en el
    formato que cada cliente espera.
    """

    @app.errorhandler(CSRFError)
    def _manejar_error_csrf(error):
        if request.path.startswith("/emergencia/"):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Token de seguridad inválido o expirado. Recarga la página e intenta de nuevo.",
                    }
                ),
                400,
            )

        flash("Tu sesión o el formulario expiraron. Intenta de nuevo.", "error")
        return redirect(request.referrer or url_for("auth.index"))


def _iniciar_scheduler(app):
    """Agenda revisar_viajes_activos() y revisar_rutas_no_iniciadas() cada
    60s (RF-3.4), en el mismo job: ambas son barridos periódicos del mismo
    tipo de dato (Viaje) y no hay razón para desacoplar su cadencia. Cada
    una tiene su propio try/except interno, así que un fallo de una no
    tumba a la otra.

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

    from app.controllers.scheduler import revisar_rutas_no_iniciadas, revisar_viajes_activos

    def _revisar_viajes_activos_job():
        with app.app_context():
            revisar_viajes_activos()
            revisar_rutas_no_iniciadas()

    scheduler.add_job(
        _revisar_viajes_activos_job,
        "interval",
        seconds=60,
        id="revisar_viajes_activos",
    )
    scheduler.start()


def _registrar_cli(app):
    """Registra los comandos de terminal de la app (RF-1.1, alta de admin).

    El alta de administrador es deliberadamente un comando de Flask CLI y
    NUNCA una ruta HTTP: es el rol más sensible del sistema (admin puede dar
    de alta cualquier otra cuenta), así que no debe existir ninguna
    superficie de ataque en el navegador para crearlo. Solo quien tiene
    acceso a la terminal del servidor puede correr `flask crear-admin`.
    """

    @app.cli.command("crear-admin")
    def crear_admin():
        """Crea una cuenta de administrador de forma interactiva."""
        from sqlalchemy.exc import IntegrityError

        from app.models.bitacora import Bitacora
        from app.models.usuario import Usuario

        nombre = click.prompt("Nombre").strip()

        nombre_usuario = click.prompt("Nombre de usuario").strip()
        while not nombre_usuario:
            click.echo("El nombre de usuario no puede estar vacío.")
            nombre_usuario = click.prompt("Nombre de usuario").strip()

        correo = click.prompt("Correo").strip()
        while not correo:
            click.echo("El correo es obligatorio.")
            correo = click.prompt("Correo").strip()

        contrasena = click.prompt(
            "Contraseña", hide_input=True, confirmation_prompt=True
        )

        usuario = Usuario(
            nombre=nombre,
            nombre_usuario=nombre_usuario,
            email=correo,
            rol="admin",
            activo=True,
        )
        usuario.set_password(contrasena)

        try:
            db.session.add(usuario)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            click.echo(
                f"Ya existe una cuenta con el nombre de usuario '{nombre_usuario}'. "
                "No se creó nada."
            )
            return

        # No hay sesión de "quien lo crea": este comando corre desde la
        # terminal, sin un current_user autenticado. id_usuario de Bitacora
        # es NOT NULL y no hay otro candidato razonable, así que se registra
        # al propio admin recién creado como autor de su alta.
        bitacora = Bitacora(
            id_usuario=usuario.id_usuario,
            accion="alta_cuenta_admin",
            descripcion=(
                f"Alta de cuenta de administrador '{usuario.nombre}' (usuario "
                f"'{usuario.nombre_usuario}') vía flask crear-admin."
            ),
            tabla_afectada="usuarios",
            registro_id=usuario.id_usuario,
        )
        db.session.add(bitacora)
        db.session.commit()

        click.echo(f"Administrador creado correctamente: {usuario.nombre_usuario}")
