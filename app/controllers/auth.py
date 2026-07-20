# Blueprint de autenticación: login, logout y redirección a la raíz
# (RF-1: Autenticación y accesos).

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models.usuario import Usuario

auth = Blueprint("auth", __name__)


def _dashboard_redirect(usuario):
    """Redirige al dashboard correspondiente según el rol del usuario (RF-1.3)."""
    if usuario.es_admin():
        return redirect(url_for("admin.dashboard"))
    if usuario.es_conductor():
        return redirect(url_for("conductor.dashboard"))
    if usuario.es_mecanico():
        return redirect(url_for("mecanico.dashboard"))
    return redirect(url_for("auth.login"))


@auth.route("/")
def index():
    """Punto de entrada: manda a login o al dashboard según haya sesión activa."""
    if current_user.is_authenticated:
        return _dashboard_redirect(current_user)
    return redirect(url_for("auth.login"))


@auth.route("/login", methods=["GET", "POST"])
def login():
    """Valida credenciales e inicia sesión (RF-1.2), o muestra el formulario de login."""
    if request.method == "POST":
        nombre_usuario = request.form.get("nombre_usuario")
        contrasena = request.form.get("contrasena")

        usuario = Usuario.query.filter_by(nombre_usuario=nombre_usuario).first()

        if usuario is None or not usuario.check_password(contrasena):
            flash("Usuario o contraseña incorrectos", "error")
            return render_template("auth/login.html")

        login_user(usuario)
        return _dashboard_redirect(usuario)

    return render_template("auth/login.html")


@auth.route("/logout")
@login_required
def logout():
    """Cierra la sesión del usuario actual (RF-1.5)."""
    logout_user()
    return redirect(url_for("auth.login"))
