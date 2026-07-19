from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models.usuario import Usuario

auth = Blueprint("auth", __name__)


def _dashboard_redirect(usuario):
    if usuario.es_admin():
        return redirect(url_for("admin.dashboard"))
    if usuario.es_conductor():
        return redirect(url_for("conductor.dashboard"))
    if usuario.es_mecanico():
        return redirect(url_for("mecanico.dashboard"))
    return redirect(url_for("auth.login"))


@auth.route("/")
def index():
    if current_user.is_authenticated:
        return _dashboard_redirect(current_user)
    return redirect(url_for("auth.login"))


@auth.route("/login", methods=["GET", "POST"])
def login():
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
    logout_user()
    return redirect(url_for("auth.login"))
