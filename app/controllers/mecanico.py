# Blueprint del rol mecánico. Pensado para alojar a futuro la gestión de
# estado vehicular y reportes de avería (RF-5).

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

mecanico = Blueprint("mecanico", __name__)


@mecanico.route("/dashboard")
@login_required
def dashboard():
    """Muestra el panel de mecánico, verificando el rol en backend (RF-1.3).

    A futuro listará los vehículos de la flota (RF-5.1).
    """
    if not current_user.es_mecanico():
        flash("No tienes permiso para acceder a esa sección", "error")
        return redirect(url_for("auth.login"))

    return render_template("mecanico/dashboard.html")
