# Blueprint del rol administrador (RF-1.4: el admin gestiona cuentas).
# Incluye el módulo de gestión de conductores (RF-2: Gestión de flota).

from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.conductor import Conductor

admin = Blueprint("admin", __name__)


def admin_required(view_func):
    """Exige sesión iniciada y rol admin (RF-1.3), igual que hacía dashboard()."""

    @wraps(view_func)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.es_admin():
            flash("No tienes permiso para acceder a esa sección", "error")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapper


def _datos_conductor_desde_formulario():
    """Lee y valida los campos del formulario de conductor.

    Retorna un dict listo para crear/actualizar un Conductor, o None (y ya
    hizo flash del error) si la fecha de vencimiento no es válida.
    """
    fecha_texto = request.form.get("fecha_vencimiento_lic", "")
    try:
        fecha_vencimiento = datetime.strptime(fecha_texto, "%Y-%m-%d").date()
    except ValueError:
        flash("La fecha de vencimiento de la licencia no es válida.", "error")
        return None

    return {
        "nombre": request.form.get("nombre", "").strip(),
        "telefono": request.form.get("telefono", "").strip(),
        "num_licencia": request.form.get("num_licencia", "").strip(),
        "fecha_vencimiento_lic": fecha_vencimiento,
        "contacto_emergencia": request.form.get("contacto_emergencia", "").strip(),
        "tel_emergencia": request.form.get("tel_emergencia", "").strip(),
    }


def _conductor_para_formulario(conductor):
    """Convierte un Conductor de BD a dict apto para prellenar el formulario HTML."""
    return {
        "nombre": conductor.nombre,
        "telefono": conductor.telefono,
        "num_licencia": conductor.num_licencia,
        "fecha_vencimiento_lic": conductor.fecha_vencimiento_lic.isoformat(),
        "contacto_emergencia": conductor.contacto_emergencia,
        "tel_emergencia": conductor.tel_emergencia,
    }


@admin.route("/dashboard")
@admin_required
def dashboard():
    """Muestra el panel de administrador."""
    return render_template("admin/dashboard.html")


@admin.route("/conductores")
@admin_required
def conductores_lista():
    """Lista todos los conductores con el estado de vigencia de su licencia (RF-2.3)."""
    conductores = Conductor.query.order_by(Conductor.nombre).all()
    return render_template("admin/conductores/lista.html", conductores=conductores)


@admin.route("/conductores/nuevo", methods=["GET", "POST"])
@admin_required
def conductores_nuevo():
    """Muestra el formulario de alta y crea el Conductor al enviarlo (RF-2.1)."""
    if request.method == "POST":
        datos = _datos_conductor_desde_formulario()
        if datos is None:
            return render_template(
                "admin/conductores/formulario.html", conductor=request.form, id_conductor=None
            )

        conductor = Conductor(**datos)
        try:
            db.session.add(conductor)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                f"Ya existe un conductor con el número de licencia '{datos['num_licencia']}'.",
                "error",
            )
            return render_template(
                "admin/conductores/formulario.html", conductor=request.form, id_conductor=None
            )

        flash(f"Conductor '{conductor.nombre}' registrado correctamente.", "success")
        return redirect(url_for("admin.conductores_lista"))

    return render_template("admin/conductores/formulario.html", conductor=None, id_conductor=None)


@admin.route("/conductores/<int:id_conductor>/editar", methods=["GET", "POST"])
@admin_required
def conductores_editar(id_conductor):
    """Muestra el formulario prellenado y actualiza los datos del conductor (RF-2.1)."""
    conductor = Conductor.query.get_or_404(id_conductor)

    if request.method == "POST":
        datos = _datos_conductor_desde_formulario()
        if datos is None:
            return render_template(
                "admin/conductores/formulario.html",
                conductor=request.form,
                id_conductor=id_conductor,
            )

        for campo, valor in datos.items():
            setattr(conductor, campo, valor)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                f"Ya existe un conductor con el número de licencia '{datos['num_licencia']}'.",
                "error",
            )
            return render_template(
                "admin/conductores/formulario.html",
                conductor=request.form,
                id_conductor=id_conductor,
            )

        flash(f"Conductor '{conductor.nombre}' actualizado correctamente.", "success")
        return redirect(url_for("admin.conductores_lista"))

    return render_template(
        "admin/conductores/formulario.html",
        conductor=_conductor_para_formulario(conductor),
        id_conductor=id_conductor,
    )
