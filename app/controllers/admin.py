# Blueprint del rol administrador (RF-1.4: el admin gestiona cuentas).

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

admin = Blueprint("admin", __name__)


@admin.route("/dashboard")
@login_required
def dashboard():
    """Muestra el panel de administrador, verificando el rol en backend (RF-1.3)."""
    if not current_user.es_admin():
        flash("No tienes permiso para acceder a esa sección", "error")
        return redirect(url_for("auth.login"))

    return render_template("admin/dashboard.html")
