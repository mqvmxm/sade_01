from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

admin = Blueprint("admin", __name__)


@admin.route("/dashboard")
@login_required
def dashboard():
    if not current_user.es_admin():
        flash("No tienes permiso para acceder a esa sección", "error")
        return redirect(url_for("auth.login"))

    return render_template("admin/dashboard.html")
