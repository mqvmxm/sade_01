# Blueprint del rol administrador (RF-1.4: el admin gestiona cuentas).
# Incluye el módulo de gestión de conductores (RF-2: Gestión de flota).

from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.alerta import Alerta
from app.models.conductor import Conductor
from app.models.vehiculo import Vehiculo
from app.models.viaje import Viaje

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


def _datos_vehiculo_desde_formulario():
    """Lee y valida los campos comunes del formulario de vehículo.

    Retorna un dict listo para crear/actualizar un Vehiculo (sin 'estado', que
    se maneja aparte), o None (y ya hizo flash del error) si el año no es válido.
    """
    anio_texto = request.form.get("anio", "")
    try:
        anio = int(anio_texto)
    except ValueError:
        flash("El año del vehículo no es válido.", "error")
        return None

    return {
        "placas": request.form.get("placas", "").strip(),
        "num_unidad": request.form.get("num_unidad", "").strip(),
        "marca": request.form.get("marca", "").strip(),
        "modelo": request.form.get("modelo", "").strip(),
        "anio": anio,
        "num_serie": request.form.get("num_serie", "").strip(),
    }


def _vehiculo_para_formulario(vehiculo):
    """Convierte un Vehiculo de BD a dict apto para prellenar el formulario HTML."""
    return {
        "placas": vehiculo.placas,
        "num_unidad": vehiculo.num_unidad,
        "marca": vehiculo.marca,
        "modelo": vehiculo.modelo,
        "anio": vehiculo.anio,
        "num_serie": vehiculo.num_serie,
        "estado": vehiculo.estado,
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


@admin.route("/vehiculos")
@admin_required
def vehiculos_lista():
    """Lista todos los vehículos registrados con su estado actual (RF-2.3)."""
    vehiculos = Vehiculo.query.order_by(Vehiculo.placas).all()
    return render_template("admin/vehiculos/lista.html", vehiculos=vehiculos)


@admin.route("/vehiculos/nuevo", methods=["GET", "POST"])
@admin_required
def vehiculos_nuevo():
    """Muestra el formulario de alta y crea el Vehiculo al enviarlo (RF-2.2).

    El estado no se pide aquí: todo vehículo nuevo inicia en 'disponible'.
    """
    if request.method == "POST":
        datos = _datos_vehiculo_desde_formulario()
        if datos is None:
            return render_template(
                "admin/vehiculos/formulario.html", vehiculo=request.form, id_vehiculo=None
            )

        vehiculo = Vehiculo(**datos)
        try:
            db.session.add(vehiculo)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                f"Ya existe un vehículo con las placas '{datos['placas']}'.",
                "error",
            )
            return render_template(
                "admin/vehiculos/formulario.html", vehiculo=request.form, id_vehiculo=None
            )

        flash(f"Vehículo '{vehiculo.placas}' registrado correctamente.", "success")
        return redirect(url_for("admin.vehiculos_lista"))

    return render_template("admin/vehiculos/formulario.html", vehiculo=None, id_vehiculo=None)


@admin.route("/vehiculos/<int:id_vehiculo>/editar", methods=["GET", "POST"])
@admin_required
def vehiculos_editar(id_vehiculo):
    """Muestra el formulario prellenado y actualiza los datos del vehículo (RF-2.2).

    El estado solo puede cambiarse aquí entre 'disponible' y 'en_taller'. Si el
    vehículo está actualmente 'en_ruta' (viaje activo, RF-5.5), el estado no es
    editable desde este formulario bajo ninguna circunstancia: cualquier POST que
    incluya el campo 'estado' se rechaza, sin importar su valor.
    """
    vehiculo = Vehiculo.query.get_or_404(id_vehiculo)

    if request.method == "POST":
        if vehiculo.estado == "en_ruta" and "estado" in request.form:
            flash(
                "No se puede modificar el estado de un vehículo en ruta; "
                "se actualizará automáticamente al finalizar el viaje activo.",
                "error",
            )
            return render_template(
                "admin/vehiculos/formulario.html",
                vehiculo=request.form,
                id_vehiculo=id_vehiculo,
            )

        datos = _datos_vehiculo_desde_formulario()
        if datos is None:
            return render_template(
                "admin/vehiculos/formulario.html",
                vehiculo=request.form,
                id_vehiculo=id_vehiculo,
            )

        if vehiculo.estado != "en_ruta":
            estado = request.form.get("estado", "")
            if estado not in ("disponible", "en_taller"):
                flash("El estado seleccionado no es válido.", "error")
                return render_template(
                    "admin/vehiculos/formulario.html",
                    vehiculo=request.form,
                    id_vehiculo=id_vehiculo,
                )
            datos["estado"] = estado

        for campo, valor in datos.items():
            setattr(vehiculo, campo, valor)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(
                f"Ya existe un vehículo con las placas '{datos['placas']}'.",
                "error",
            )
            return render_template(
                "admin/vehiculos/formulario.html",
                vehiculo=request.form,
                id_vehiculo=id_vehiculo,
            )

        flash(f"Vehículo '{vehiculo.placas}' actualizado correctamente.", "success")
        return redirect(url_for("admin.vehiculos_lista"))

    return render_template(
        "admin/vehiculos/formulario.html",
        vehiculo=_vehiculo_para_formulario(vehiculo),
        id_vehiculo=id_vehiculo,
    )


@admin.route("/viajes")
@admin_required
def viajes_lista():
    """Lista los viajes 'activo', 'alerta' o 'emergencia' para monitoreo del administrador (RF-3/RF-4).

    Las emergencias reales van siempre primero, sin importar su hora_salida:
    son lo más urgente y no deben poder quedar enterradas debajo de simples
    retrasos o viajes normales más recientes.
    """
    prioridad_estado = case(
        (Viaje.estado == "emergencia", 0),
        (Viaje.estado == "alerta", 1),
        else_=2,
    )
    viajes = (
        Viaje.query.filter(Viaje.estado.in_(["activo", "alerta", "emergencia"]))
        .order_by(prioridad_estado, Viaje.hora_salida)
        .all()
    )
    return render_template("admin/viajes/lista.html", viajes=viajes)


@admin.route("/alertas")
@admin_required
def alertas_lista():
    """Lista las alertas sin atender, más recientes primero (RF-3.5)."""
    alertas = (
        Alerta.query.filter_by(atendida=False)
        .order_by(Alerta.generada_en.desc())
        .all()
    )
    return render_template("admin/alertas/lista.html", alertas=alertas)


@admin.route("/alertas/<int:id_alerta>/atender", methods=["POST"])
@admin_required
def alertas_atender(id_alerta):
    """Marca una alerta como atendida (RF-3.5)."""
    alerta = Alerta.query.get_or_404(id_alerta)
    alerta.atendida = True
    alerta.atendida_en = datetime.now()
    db.session.commit()

    flash("Alerta marcada como atendida.", "success")
    return redirect(url_for("admin.alertas_lista"))
